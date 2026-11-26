"""Readers turn one raw file into a LazyFrame: one class per file format.

A ``SourceSpec`` holds a reader instance, so the build pipeline never branches on
file type. INMET CSV and ERA5 readers are added here when that data is downloaded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import polars as pl


class RawReader(Protocol):
    def scan(self, path: Path) -> pl.LazyFrame:
        """Lazily read one raw file with its columns and dtypes as stored."""
        ...


@dataclass(frozen=True)
class ParquetReader:
    """All ONS datasets are downloaded as Parquet (see raw/SOURCES.md)."""

    def scan(self, path: Path) -> pl.LazyFrame:
        return pl.scan_parquet(path)


class ArcGisResponseError(ValueError):
    """The file is an ArcGIS error response, or a field type the reader doesn't know."""


# ArcGIS field types -> Polars. Dates are milliseconds since 1970-01-01 UTC.
ARCGIS_DTYPES: dict[str, pl.DataType] = {
    "esriFieldTypeOID": pl.Int64,
    "esriFieldTypeSmallInteger": pl.Int16,
    "esriFieldTypeInteger": pl.Int32,
    "esriFieldTypeSingle": pl.Float32,
    "esriFieldTypeDouble": pl.Float64,
    "esriFieldTypeString": pl.String,
    "esriFieldTypeDate": pl.Datetime("ms", time_zone="UTC"),
}

POINT_GEOMETRY = "esriGeometryPoint"
GEOMETRY_X = "geometry_x"
GEOMETRY_Y = "geometry_y"
GEOMETRY_JSON = "geometry_json"


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

    def scan(self, path: Path) -> pl.LazyFrame:
        response = json.loads(path.read_text(encoding="utf-8"))
        if "error" in response:
            raise ArcGisResponseError(
                f"{path.name}: ArcGIS error response {response['error']}"
            )

        features = response["features"]
        columns = [
            _attribute_column(field, _values(features, field["name"]), path)
            for field in response["fields"]
        ]

        geometries = [feature.get("geometry") for feature in features]
        columns.extend(_geometry_columns(response.get("geometryType"), geometries))

        return pl.DataFrame(columns).lazy()


def _values(features: list[dict], name: str) -> list[Any]:
    return [feature["attributes"].get(name) for feature in features]


def _attribute_column(
    field: dict[str, Any], values: list[Any], path: Path
) -> pl.Series:
    name, arcgis_type = field["name"], field["type"]
    if arcgis_type not in ARCGIS_DTYPES:
        raise ArcGisResponseError(
            f"{path.name}: field {name!r} has unsupported type {arcgis_type}"
        )

    dtype = ARCGIS_DTYPES[arcgis_type]
    if isinstance(dtype, pl.Datetime):
        epoch_ms = pl.Series(name, values, dtype=pl.Int64, strict=True)
        return epoch_ms.cast(pl.Datetime("ms")).dt.replace_time_zone("UTC")

    return pl.Series(name, values, dtype=dtype, strict=True)


def _geometry_columns(
    geometry_type: str | None, geometries: list[dict | None]
) -> list[pl.Series]:
    if geometry_type is None:
        return []

    if geometry_type == POINT_GEOMETRY:
        return [
            _coordinate(GEOMETRY_X, geometries, "x"),
            _coordinate(GEOMETRY_Y, geometries, "y"),
        ]

    text = [json.dumps(g, separators=(",", ":")) if g else None for g in geometries]
    return [pl.Series(GEOMETRY_JSON, text, dtype=pl.String)]


def _coordinate(name: str, geometries: list[dict | None], axis: str) -> pl.Series:
    values = [geometry[axis] if geometry else None for geometry in geometries]
    return pl.Series(name, values, dtype=pl.Float64, strict=True)
