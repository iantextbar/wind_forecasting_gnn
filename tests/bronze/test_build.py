import json
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from scripts.bronze.build import (
    META_FILENAME,
    BronzeBuildError,
    build_all,
    build_bronze,
    unclaimed_raw_files,
)
from scripts.bronze.schemas import INSTANT
from scripts.bronze.specs import SourceSpec
from scripts.utils.checks import OverlapError, SchemaMismatchError
from scripts.utils.paths import DataPaths

SPEC = SourceSpec(
    name="toy",
    # Mirrors fator_capacidade: two naming schemes whose names don't sort by time.
    patterns=("TOY_*.parquet", "TOY-2_*.parquet"),
    schema={"din_instante": INSTANT, "id_ons": pl.String, "val": pl.Float64},
    sort_keys=("din_instante", "id_ons"),
    unique_keys=("id_ons", "din_instante"),
    time_column="din_instante",
)


def instants(*hours: int, year: int = 2021) -> pl.Series:
    return pl.Series([datetime(year, 12, 31, hour) for hour in hours], dtype=INSTANT)


def write_raw(paths: DataPaths, name: str, frame: pl.DataFrame) -> Path:
    folder = paths.raw / SPEC.name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    frame.write_parquet(path)
    return path


@pytest.fixture
def paths(tmp_path: Path) -> DataPaths:
    paths = DataPaths(tmp_path)
    # Yearly scheme: decimal strings, unsorted, an empty string, a duplicate key.
    write_raw(
        paths,
        "TOY_2021.parquet",
        pl.DataFrame(
            {
                "din_instante": instants(23, 1, 1, 1),
                "id_ons": ["B", "B", "A", "A"],
                "val": ["0.5", "0E-8", "", "0.7"],
            }
        ),
    )
    # Monthly scheme, later period: Float64 (schema drift), columns in another order.
    write_raw(
        paths,
        "TOY-2_2022_01.parquet",
        pl.DataFrame(
            {
                "id_ons": ["A"],
                "val": [0.9],
                "din_instante": pl.Series([datetime(2022, 1, 1, 0)], dtype=INSTANT),
            }
        ),
    )
    (paths.raw / SPEC.name / "DicionarioDados_Toy.pdf").write_bytes(b"%PDF")
    return paths


def read_bronze(paths: DataPaths) -> pl.DataFrame:
    return pl.scan_parquet(paths.bronze / SPEC.name / "*.parquet").collect()


def read_meta(paths: DataPaths) -> dict:
    return json.loads((paths.bronze / SPEC.name / META_FILENAME).read_text())


def test_parts_are_time_ordered_and_source_is_globally_sorted(paths):
    build_bronze(SPEC, paths)
    meta = read_meta(paths)
    assert [part["raw_file"] for part in meta["parts"]] == [
        "TOY_2021.parquet",
        "TOY-2_2022_01.parquet",
    ]
    bronze = read_bronze(paths)
    assert bronze.equals(bronze.sort(SPEC.sort_keys, maintain_order=True))
    assert bronze.columns == list(SPEC.schema)
    assert bronze.schema == pl.Schema(SPEC.schema)


def test_timestamps_and_their_values_are_unchanged(paths):
    """No leakage and no timezone shift in bronze: every row keeps its own timestamp,
    timestamps stay naive, and no value moves to another instant."""
    build_bronze(SPEC, paths)
    bronze = read_bronze(paths)
    assert bronze.schema["din_instante"] == pl.Datetime("ns", time_zone=None)
    expected = [
        (datetime(2021, 12, 31, 1), "A", None),
        (datetime(2021, 12, 31, 1), "A", 0.7),
        (datetime(2021, 12, 31, 1), "B", 0.0),
        (datetime(2021, 12, 31, 23), "B", 0.5),
        (datetime(2022, 1, 1, 0), "A", 0.9),
    ]
    assert bronze.rows() == expected


def test_duplicates_and_empty_strings_are_reported_not_dropped(paths):
    report = build_bronze(SPEC, paths)
    assert report.rows == 5
    assert report.duplicate_key_rows == 1
    meta = read_meta(paths)
    assert meta["empty_strings_to_null"] == {"val": 1}
    assert meta["parts"][0]["casts"] == {"val": "String -> Float64"}
    assert meta["parts"][1]["casts"] == {}


def test_unchanged_inputs_are_skipped_and_changed_inputs_rebuilt(paths):
    assert build_bronze(SPEC, paths).status == "built"
    assert build_bronze(SPEC, paths).status == "skipped"
    assert build_bronze(SPEC, paths, force=True).status == "built"
    write_raw(
        paths,
        "TOY-2_2022_01.parquet",
        pl.DataFrame(
            {
                "din_instante": pl.Series([datetime(2022, 1, 1, 0)], dtype=INSTANT),
                "id_ons": ["A"],
                "val": [0.95],  # an ONS revision
            }
        ),
    )
    assert build_bronze(SPEC, paths).status == "built"
    assert read_bronze(paths)["val"][-1] == 0.95


def test_overlapping_files_fail_and_leave_previous_output(paths):
    build_bronze(SPEC, paths)
    before = read_bronze(paths)
    write_raw(
        paths,
        "TOY-2_2021_12.parquet",
        pl.DataFrame(
            {
                "din_instante": instants(5),
                "id_ons": ["A"],
                "val": [0.1],
            }
        ),
    )
    with pytest.raises(OverlapError):
        build_bronze(SPEC, paths)
    assert read_bronze(paths).equals(before)
    assert not any(path.name.startswith(".") for path in paths.bronze.iterdir())


def test_unexpected_column_fails_the_build(paths):
    write_raw(
        paths,
        "TOY-2_2022_02.parquet",
        pl.DataFrame(
            {
                "din_instante": pl.Series([datetime(2022, 2, 1)], dtype=INSTANT),
                "id_ons": ["A"],
                "val": [0.1],
                "new_column": [1],
            }
        ),
    )
    with pytest.raises(SchemaMismatchError, match="new_column"):
        build_bronze(SPEC, paths)


def test_unparseable_value_fails_the_build(paths):
    write_raw(
        paths,
        "TOY_2020.parquet",
        pl.DataFrame(
            {
                "din_instante": instants(1, year=2020),
                "id_ons": ["A"],
                "val": ["n/a"],
            }
        ),
    )
    with pytest.raises(BronzeBuildError, match="TOY_2020"):
        build_bronze(SPEC, paths)


def test_build_all_continues_after_a_failure_then_raises(paths):
    broken = SourceSpec(**{**SPEC.__dict__, "name": "missing"})
    with pytest.raises(BronzeBuildError, match="missing"):
        build_all({"missing": broken, "toy": SPEC}, paths)
    assert (paths.bronze / SPEC.name / META_FILENAME).is_file()


def test_rebuild_is_deterministic(paths):
    build_bronze(SPEC, paths)
    first = read_bronze(paths)
    build_bronze(SPEC, paths, force=True)
    assert read_bronze(paths).equals(first)


# Static registry split into pages that share one raw folder, like SIGEL layers.
PAGED = SourceSpec(
    name="paged",
    raw_folder="registry/20260101T000000Z",
    patterns=("layer_a_page_*.parquet",),
    companions=("manifest.csv",),
    schema={"id": pl.Int64, "code": pl.String},
    sort_keys=("id",),
    unique_keys=("code",),
    time_column=None,
)
OTHER_LAYER = SourceSpec(
    **{**PAGED.__dict__, "name": "other", "patterns": ("layer_b_page_*.parquet",)}
)


@pytest.fixture
def paged_paths(tmp_path: Path) -> DataPaths:
    paths = DataPaths(tmp_path)
    folder = paths.raw / PAGED.raw_path
    folder.mkdir(parents=True)
    # The same code appears on two pages: invisible to a per-page count.
    pl.DataFrame({"id": [2, 1], "code": ["X", "Y"]}).write_parquet(
        folder / "layer_a_page_000.parquet"
    )
    pl.DataFrame({"id": [3], "code": ["X"]}).write_parquet(
        folder / "layer_a_page_001.parquet"
    )
    pl.DataFrame({"id": [9], "code": ["Z"]}).write_parquet(
        folder / "layer_b_page_000.parquet"
    )
    (folder / "manifest.csv").write_text("file,sha256\n")
    (folder / ".gitkeep").write_text("")
    return paths


def test_spec_reads_its_raw_folder_and_writes_under_its_name(paged_paths):
    build_bronze(PAGED, paged_paths)
    bronze = pl.read_parquet(paged_paths.bronze / "paged" / "*.parquet")
    assert bronze["id"].to_list() == [1, 2, 3]


def test_duplicates_across_pages_are_counted_without_a_time_column(paged_paths):
    report = build_bronze(PAGED, paged_paths)
    assert report.duplicate_key_rows == 1
    assert report.rows == 3


def test_files_claimed_by_any_spec_sharing_the_folder_are_not_unclaimed(paged_paths):
    folder = paged_paths.raw / PAGED.raw_path
    assert unclaimed_raw_files([PAGED, OTHER_LAYER], paged_paths.raw) == {}
    assert unclaimed_raw_files([PAGED], paged_paths.raw) == {
        PAGED.raw_path: ["layer_b_page_000.parquet"]
    }
    (folder / "surprise.json").write_text("{}")
    assert unclaimed_raw_files([PAGED, OTHER_LAYER], paged_paths.raw) == {
        PAGED.raw_path: ["surprise.json"]
    }


def test_time_ordered_spec_must_include_time_in_unique_keys():
    with pytest.raises(ValueError, match="unique_keys must include the time column"):
        SourceSpec(**{**SPEC.__dict__, "unique_keys": ("id_ons",)})


def test_metadata_names_the_run_log(paths):
    build_bronze(SPEC, paths, run_log="data/bronze/20261124T172500Z.log")
    assert read_meta(paths)["run_log"] == "data/bronze/20261124T172500Z.log"
