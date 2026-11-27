"""ArcGIS REST ``query`` responses (``f=json``), as served for the SIGEL layers."""

from __future__ import annotations

import polars as pl

# ArcGIS field types -> Polars. Dates are milliseconds since 1970-01-01 UTC.
DTYPES: dict[str, pl.DataType] = {
    "esriFieldTypeOID": pl.Int64,
    "esriFieldTypeSmallInteger": pl.Int16,
    "esriFieldTypeInteger": pl.Int32,
    "esriFieldTypeSingle": pl.Float32,
    "esriFieldTypeDouble": pl.Float64,
    "esriFieldTypeString": pl.String,
    "esriFieldTypeDate": pl.Datetime("ms", time_zone="UTC"),
}

POINT_GEOMETRY = "esriGeometryPoint"

# Columns the reader adds for each feature's geometry.
GEOMETRY_X = "geometry_x"
GEOMETRY_Y = "geometry_y"
GEOMETRY_JSON = "geometry_json"
