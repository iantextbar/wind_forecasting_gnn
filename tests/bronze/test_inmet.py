"""INMET readers and the INMET specs, on small archives shaped like the real ones."""

import json
import zipfile
from datetime import date, time
from pathlib import Path

import polars as pl
import pytest

from scripts.bronze.build import META_FILENAME, build_bronze, unclaimed_raw_files
from scripts.bronze.raw_formats import inmet
from scripts.bronze.raw_formats.inmet import OBSERVATION_COLUMNS, STATION_COLUMNS
from scripts.bronze.readers import (
    InmetFormatError,
    InmetObservationReader,
    InmetStationReader,
)
from scripts.bronze.specs import INMET_ESTACOES, INMET_HORARIO
from scripts.utils.paths import DataPaths

# Copied from real files: 2009-2018 spelling, and 2020 onwards.
HEADER_2009 = (
    "DATA (YYYY-MM-DD);HORA (UTC);PRECIPITAÇÃO TOTAL, HORÁRIO (mm);"
    "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB);"
    "PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB);"
    "PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB);RADIACAO GLOBAL (KJ/m²);"
    "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);"
    "TEMPERATURA DO PONTO DE ORVALHO (°C);"
    "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C);"
    "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C);"
    "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C);"
    "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C);"
    "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%);"
    "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%);UMIDADE RELATIVA DO AR, HORARIA (%);"
    "VENTO, DIREÇÃO HORARIA (gr) (° (gr));VENTO, RAJADA MAXIMA (m/s);"
    "VENTO, VELOCIDADE HORARIA (m/s);"
)
HEADER_2020 = HEADER_2009.replace(
    "DATA (YYYY-MM-DD);HORA (UTC)", "Data;Hora UTC"
).replace("(KJ/m²)", "(Kj/m²)")
KEYS_2009 = (
    "REGIÃO:",
    "UF:",
    "ESTAÇÃO:",
    "CODIGO (WMO):",
    "LATITUDE:",
    "LONGITUDE:",
    "ALTITUDE:",
    "DATA DE FUNDAÇÃO (YYYY-MM-DD):",
)
KEYS_2020 = tuple(
    key.replace("Ã", "A").replace("Ç", "C").replace(" (YYYY-MM-DD)", "")
    for key in KEYS_2009
)
MEASUREMENTS = len(OBSERVATION_COLUMNS) - 2


def row(day: str, hour: str, wind: str) -> str:
    """One hourly row: wind speed last, every other measurement 1."""
    return ";".join([day, hour, *["1"] * (MEASUREMENTS - 1), wind]) + ";"


def station_csv(
    code: str,
    rows: list[str],
    *,
    new: bool,
    altitude: str = "1159,54",
    header: str | None = None,
) -> bytes:
    keys = KEYS_2020 if new else KEYS_2009
    values = ("CO", "DF", "BRASÍLIA", code, "-15,78944444", "-47,92583332")
    values += (altitude, "07/05/00" if new else "2000-05-07")
    lines = [f"{key};{value}" for key, value in zip(keys, values, strict=True)]
    lines.append(header or (HEADER_2020 if new else HEADER_2009))
    return ("\n".join([*lines, *rows]) + "\n").encode("latin-1")


def member_name(code: str, year: int) -> str:
    return f"INMET_CO_DF_{code}_BRASILIA_01-01-{year}_A_31-12-{year}.CSV"


def write_archive(folder: Path, year: int, members: dict[str, bytes]) -> Path:
    """An archive; years up to 2019 keep their CSVs in a ``<year>/`` folder."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{year}.zip"
    prefix = f"{year}/" if year <= 2019 else ""
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(prefix + name, content)
    return path


def chunks(path: Path) -> list[pl.DataFrame]:
    return [chunk.collect() for chunk in InmetObservationReader().scan(path)]


def test_observations_are_one_text_chunk_per_station_in_either_layout(tmp_path):
    old = write_archive(
        tmp_path,
        2018,
        {
            member_name("A002", 2018): station_csv(
                "A002", [row("2018-01-01", "00:00", ",8")], new=False
            ),
            member_name("A001", 2018): station_csv(
                "A001", [row("2018-01-01", "00:00", "-9999")], new=False
            ),
        },
    )
    new = write_archive(
        tmp_path,
        2020,
        {
            member_name("A001", 2020): station_csv(
                "A001", [row("2020/01/01", "2300 UTC", "")], new=True
            )
        },
    )

    first, second = chunks(old)
    assert first.columns == ["codigo_wmo", *OBSERVATION_COLUMNS]
    assert set(first.schema.dtypes()) == {pl.String}
    assert first.row(0)[:3] == ("A001", "2018-01-01", "00:00")
    assert first["vento_velocidade"].to_list() == ["-9999"]
    assert second["vento_velocidade"].to_list() == [",8"]  # text as written

    (only,) = chunks(new)
    assert only.row(0)[:3] == ("A001", "2020/01/01", "2300 UTC")
    assert only["vento_velocidade"].to_list() == [""]


def test_unknown_column_header_fails(tmp_path):
    drifted = HEADER_2020.replace("Hora UTC", "Hora (UTC)")
    path = write_archive(
        tmp_path,
        2021,
        {
            member_name("A001", 2021): station_csv(
                "A001", [row("2021/01/01", "0000 UTC", "1")], new=True, header=drifted
            )
        },
    )
    with pytest.raises(InmetFormatError, match="unknown column header"):
        chunks(path)


def test_station_code_must_match_the_file_name(tmp_path):
    content = station_csv("A999", [row("2021/01/01", "0000 UTC", "1")], new=True)
    path = write_archive(tmp_path, 2021, {member_name("A001", 2021): content})
    with pytest.raises(InmetFormatError, match="differs"):
        chunks(path)


def test_a_short_row_fails_instead_of_reading_as_missing(tmp_path):
    short = row("2021/01/01", "0100 UTC", "1").rsplit(";", 3)[0] + ";"
    content = station_csv("A001", [row("2021/01/01", "0000 UTC", "1"), short], new=True)
    path = write_archive(tmp_path, 2021, {member_name("A001", 2021): content})
    with pytest.raises(InmetFormatError, match="too few fields"):
        chunks(path)


def test_a_value_after_the_last_column_fails(tmp_path):
    content = station_csv("A001", [row("2021/01/01", "0000 UTC", "1") + "x"], new=True)
    path = write_archive(tmp_path, 2021, {member_name("A001", 2021): content})
    with pytest.raises(InmetFormatError, match="after the last column"):
        chunks(path)


def test_a_member_outside_the_naming_pattern_fails(tmp_path):
    content = station_csv("A001", [row("2021/01/01", "0000 UTC", "1")], new=True)
    path = write_archive(tmp_path, 2021, {"notes.CSV": content})
    with pytest.raises(InmetFormatError, match="pattern"):
        chunks(path)


def test_stations_are_one_row_per_file_with_the_period_from_its_name(tmp_path):
    path = write_archive(
        tmp_path,
        2018,
        {
            member_name("A001", 2018): station_csv(
                "A001", [row("2018-01-01", "00:00", "1")], new=False, altitude="F"
            )
        },
    )
    (chunk,) = InmetStationReader().scan(path)
    frame = chunk.collect()
    assert frame.columns == list(STATION_COLUMNS)
    assert frame.row(0, named=True) == {
        "arquivo": member_name("A001", 2018),
        "regiao": "CO",
        "uf": "DF",
        "estacao": "BRASÍLIA",  # Latin-1 decoded
        "codigo_wmo": "A001",
        "latitude": "-15,78944444",
        "longitude": "-47,92583332",
        "altitude": "F",
        "data_fundacao": "2000-05-07",
        "periodo_inicio": "01-01-2018",
        "periodo_fim": "31-12-2018",
    }


@pytest.fixture
def inmet_paths(tmp_path: Path) -> DataPaths:
    """Two yearly archives, one per era, with both missing-value spellings."""
    paths = DataPaths(tmp_path)
    folder = paths.raw / INMET_HORARIO.raw_path
    write_archive(
        folder,
        2018,
        {
            member_name("A002", 2018): station_csv(
                "A002",
                [row("2018-12-31", "23:00", "2,5"), row("2018-12-31", "00:00", ",8")],
                new=False,
                altitude="F",
            ),
            member_name("A001", 2018): station_csv(
                "A001", [row("2018-12-31", "23:00", "-9999")], new=False
            ),
        },
    )
    write_archive(
        folder,
        2020,
        {
            member_name("A001", 2020): station_csv(
                "A001",
                [
                    row("2020/01/01", "0000 UTC", "3,1"),
                    row("2020/01/01", "0100 UTC", ""),
                ],
                new=True,
            )
        },
    )
    (folder / "SHA256SUMS").write_text("")
    return paths


def read_source(paths: DataPaths, name: str) -> tuple[pl.DataFrame, dict]:
    folder = paths.bronze / name
    meta = json.loads((folder / META_FILENAME).read_text())
    return pl.read_parquet(folder / "*.parquet"), meta


def test_observations_build_typed_sorted_and_with_hours_unchanged(inmet_paths):
    """No leakage and no timezone shift: each value keeps its own UTC date and hour,
    in both spellings, and nothing moves to another station or instant."""
    report = build_bronze(INMET_HORARIO, inmet_paths)
    bronze, meta = read_source(inmet_paths, INMET_HORARIO.name)

    assert report.parts == 2
    assert bronze.schema["vento_velocidade"] == pl.Float32
    assert bronze.select(
        "codigo_wmo", "data", "hora_utc", "vento_velocidade"
    ).rows() == [
        ("A002", date(2018, 12, 31), time(0), pytest.approx(0.8)),
        ("A001", date(2018, 12, 31), time(23), None),
        ("A002", date(2018, 12, 31), time(23), 2.5),
        ("A001", date(2020, 1, 1), time(0), pytest.approx(3.1)),
        ("A001", date(2020, 1, 1), time(1), None),
    ]
    assert meta["null_tokens_to_null"]["vento_velocidade"] == {"": 1, "-9999": 1}
    old, new = meta["parts"]
    assert old["casts"]["data"] == "String -> Date (%Y-%m-%d)"
    assert new["casts"]["hora_utc"] == "String -> Time (%H%M UTC)"


def test_stations_build_one_row_per_file_with_declared_tokens_as_null(inmet_paths):
    build_bronze(INMET_ESTACOES, inmet_paths)
    bronze, meta = read_source(inmet_paths, INMET_ESTACOES.name)

    assert bronze.select("codigo_wmo", "periodo_inicio", "altitude").rows() == [
        ("A001", date(2018, 1, 1), pytest.approx(1159.54)),
        ("A002", date(2018, 1, 1), None),
        ("A001", date(2020, 1, 1), pytest.approx(1159.54)),
    ]
    assert meta["null_tokens_to_null"] == {"altitude": {"F": 1}}
    assert bronze["data_fundacao"].to_list() == ["2000-05-07", "2000-05-07", "07/05/00"]


def test_the_two_inmet_specs_claim_every_file_in_the_folder(inmet_paths):
    specs = [INMET_HORARIO, INMET_ESTACOES]
    assert unclaimed_raw_files(specs, inmet_paths.raw) == {}


def test_every_header_spelling_has_one_field_per_column_plus_the_trailing_one():
    for spelling in inmet.COLUMN_HEADER_SPELLINGS:
        assert spelling.split(inmet.SEPARATOR)[-1] == ""
        assert len(spelling.split(inmet.SEPARATOR)) == len(OBSERVATION_COLUMNS) + 1
    for keys in inmet.STATION_KEY_SPELLINGS:
        assert len(keys) == len(inmet.STATION_FIELDS) == inmet.STATION_LINES
