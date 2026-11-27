"""Readers turn one raw file into chunks of rows: one class per file format.

A ``SourceSpec`` holds a reader instance, so the build pipeline never branches on
file type. Most formats yield one chunk per file. An archive of many tables (INMET)
yields one chunk per table, so the build casts each chunk before the next is
decompressed and peak memory stays at the typed file.

What each format looks like (spellings, field types, naming patterns) is described
in ``scripts.bronze.raw_formats``; this module holds the code that reads it.
"""

from __future__ import annotations

import json
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import polars as pl

from scripts.bronze.raw_formats import arcgis, inmet


class RawReader(Protocol):
    def scan(self, path: Path) -> Iterator[pl.LazyFrame]:
        """One raw file as one or more chunks, each with the columns and dtypes as
        stored. Chunks are produced lazily, one at a time."""
        ...


# --- Parquet (ONS) ---


@dataclass(frozen=True)
class ParquetReader:
    """All ONS datasets are downloaded as Parquet (see raw/SOURCES.md)."""

    def scan(self, path: Path) -> Iterator[pl.LazyFrame]:
        yield pl.scan_parquet(path)


# --- ArcGIS query responses (ANEEL SIGEL) ---


class ArcGisResponseError(ValueError):
    """The file is an ArcGIS error response, or a field type the reader doesn't know."""


@dataclass(frozen=True)
class ArcGisQueryReader:
    """One page of an ArcGIS REST ``query`` response (``f=json``), one row per feature.

    Column dtypes come from the response's own ``fields`` list, the way a Parquet
    file declares its schema; every value is converted strictly, so a value that
    doesn't fit its declared type raises instead of becoming null.

    Geometry, returned beside the attributes:
    - points become ``geometry_x``/``geometry_y`` (Float64) in the response's
      spatial reference: degrees longitude/latitude when requested with
      ``outSR=4326``;
    - any other geometry (polygons, lines) becomes ``geometry_json``, its JSON
      text, so nothing is lost; parsing it is left to whoever uses it;
    - no columns are added when the response carries no geometry type.
    A feature without geometry gets nulls.
    """

    def scan(self, path: Path) -> Iterator[pl.LazyFrame]:
        response = json.loads(path.read_text(encoding="utf-8"))
        if "error" in response:
            raise ArcGisResponseError(
                f"{path.name}: ArcGIS error response {response['error']}"
            )

        features = response["features"]
        columns = [
            _arcgis_attribute(field, _arcgis_values(features, field["name"]), path)
            for field in response["fields"]
        ]

        geometries = [feature.get("geometry") for feature in features]
        columns.extend(_arcgis_geometry(response.get("geometryType"), geometries))

        yield pl.DataFrame(columns).lazy()


def _arcgis_values(features: list[dict], name: str) -> list[Any]:
    return [feature["attributes"].get(name) for feature in features]


def _arcgis_attribute(
    field: dict[str, Any], values: list[Any], path: Path
) -> pl.Series:
    name, arcgis_type = field["name"], field["type"]
    if arcgis_type not in arcgis.DTYPES:
        raise ArcGisResponseError(
            f"{path.name}: field {name!r} has unsupported type {arcgis_type}"
        )

    dtype = arcgis.DTYPES[arcgis_type]
    if isinstance(dtype, pl.Datetime):
        epoch_ms = pl.Series(name, values, dtype=pl.Int64, strict=True)
        return epoch_ms.cast(pl.Datetime("ms")).dt.replace_time_zone("UTC")

    return pl.Series(name, values, dtype=dtype, strict=True)


def _arcgis_geometry(
    geometry_type: str | None, geometries: list[dict | None]
) -> list[pl.Series]:
    if geometry_type is None:
        return []

    if geometry_type == arcgis.POINT_GEOMETRY:
        return [
            _arcgis_coordinate(arcgis.GEOMETRY_X, geometries, "x"),
            _arcgis_coordinate(arcgis.GEOMETRY_Y, geometries, "y"),
        ]

    text = [json.dumps(g, separators=(",", ":")) if g else None for g in geometries]
    return [pl.Series(arcgis.GEOMETRY_JSON, text, dtype=pl.String)]


def _arcgis_coordinate(
    name: str, geometries: list[dict | None], axis: str
) -> pl.Series:
    values = [geometry[axis] if geometry else None for geometry in geometries]
    return pl.Series(name, values, dtype=pl.Float64, strict=True)


# --- INMET station archives ---


class InmetFormatError(ValueError):
    """An INMET archive or CSV doesn't follow the surveyed format."""


@dataclass(frozen=True)
class InmetObservationReader:
    """Hourly observations: one chunk per station CSV, all columns as text.

    The readers only take the format apart: archive layout, station lines, column
    header, row shape. Values stay text exactly as written, for the spec's
    ``TextEncoding``.

    Columns: ``codigo_wmo`` (from the station lines), then
    ``raw_formats.inmet.OBSERVATION_COLUMNS``.
    """

    def scan(self, path: Path) -> Iterator[pl.LazyFrame]:
        for name, raw in _inmet_members(path, header_only=False):
            member = _inmet_parse(path, name, raw)
            yield _inmet_observations(member).lazy()


@dataclass(frozen=True)
class InmetStationReader:
    """Station lines: one row per station CSV, one chunk per archive, all as text.

    Columns: ``raw_formats.inmet.STATION_COLUMNS``. Only each CSV's header is
    decompressed.
    """

    def scan(self, path: Path) -> Iterator[pl.LazyFrame]:
        rows = [
            _inmet_station_row(_inmet_parse(path, name, raw))
            for name, raw in _inmet_members(path, header_only=True)
        ]
        schema = dict.fromkeys(inmet.STATION_COLUMNS, pl.String)
        yield pl.DataFrame(rows, schema=schema, orient="row").lazy()


@dataclass(frozen=True)
class _InmetMember:
    """One station CSV taken apart."""

    context: str
    file_name: str
    name_fields: re.Match[str]  # inmet.MEMBER_NAME groups
    station: dict[str, str]
    body: bytes  # the hourly rows, still ";"-separated


def _inmet_members(path: Path, *, header_only: bool) -> Iterator[tuple[str, bytes]]:
    """``(file name, bytes)`` per CSV in the archive, whatever folder holds it."""
    with zipfile.ZipFile(path) as archive:
        files = [info for info in archive.infolist() if not info.is_dir()]
        names = [Path(info.filename).name for info in files]
        if len(set(names)) != len(names):
            raise InmetFormatError(f"{path.name}: two members share a file name")

        for name, info in sorted(zip(names, files, strict=True)):
            if header_only:
                with archive.open(info) as handle:
                    lines = (handle.readline() for _ in range(inmet.HEADER_LINES))
                    raw = b"".join(lines)
            else:
                raw = archive.read(info)
            yield name, raw


def _inmet_parse(path: Path, name: str, raw: bytes) -> _InmetMember:
    context = f"{path.name}/{name}"
    match = inmet.MEMBER_NAME.match(name)
    if match is None:
        raise InmetFormatError(f"{context}: file name doesn't follow INMET's pattern")

    parts = raw.split(inmet.NEWLINE, inmet.HEADER_LINES)
    if len(parts) <= inmet.HEADER_LINES:
        raise InmetFormatError(
            f"{context}: fewer than {inmet.HEADER_LINES} header lines"
        )

    header = [
        line.decode(inmet.TEXT_ENCODING).rstrip("\r")
        for line in parts[: inmet.HEADER_LINES]
    ]
    station = _inmet_station_lines(context, header[: inmet.STATION_LINES])
    if station[inmet.STATION_CODE] != match["codigo"]:
        raise InmetFormatError(
            f"{context}: station code {station[inmet.STATION_CODE]!r} in the file "
            f"differs from {match['codigo']!r} in its name"
        )

    column_header = header[inmet.STATION_LINES]
    if column_header not in inmet.COLUMN_HEADER_SPELLINGS:
        raise InmetFormatError(f"{context}: unknown column header {column_header!r}")

    return _InmetMember(
        context=context,
        file_name=name,
        name_fields=match,
        station=station,
        body=parts[-1],
    )


def _inmet_station_lines(context: str, lines: list[str]) -> dict[str, str]:
    cells = [line.split(inmet.SEPARATOR) for line in lines]
    if any(len(pair) != 2 for pair in cells):
        raise InmetFormatError(f"{context}: station lines aren't key;value pairs")

    keys = tuple(key for key, _ in cells)
    if keys not in inmet.STATION_KEY_SPELLINGS:
        raise InmetFormatError(f"{context}: unknown station keys {keys}")

    values = (value for _, value in cells)
    return dict(zip(inmet.STATION_FIELDS, values, strict=True))


def _inmet_observations(member: _InmetMember) -> pl.DataFrame:
    columns = inmet.OBSERVATION_COLUMNS
    frame = pl.read_csv(
        member.body,
        has_header=False,
        new_columns=[*columns, inmet.TRAILING_FIELD],
        separator=inmet.SEPARATOR,
        quote_char=None,
        infer_schema=False,  # every column as text; casting.py types them
        empty_string_is_null=False,  # "" is a value: the null token since 2019
    )

    # Polars raises on a row with too many fields but pads a short one with "",
    # which would pass as missing values. Every row has exactly one separator per
    # column (the last one before the trailing field); none has more, so the total
    # only adds up if none has fewer.
    separators = member.body.count(inmet.SEPARATOR.encode())
    if separators != len(columns) * frame.height:
        raise InmetFormatError(f"{member.context}: some rows have too few fields")
    if (frame[inmet.TRAILING_FIELD] != "").any():
        raise InmetFormatError(f"{member.context}: a value after the last column")

    code = pl.lit(member.station[inmet.STATION_CODE], dtype=pl.String)
    return frame.select(code.alias(inmet.STATION_CODE), *columns)


def _inmet_station_row(member: _InmetMember) -> tuple[str, ...]:
    station = (member.station[field] for field in inmet.STATION_FIELDS)
    period = (member.name_fields["inicio"], member.name_fields["fim"])
    return (member.file_name, *station, *period)
