import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from scripts.bronze.readers import ArcGisQueryReader, ArcGisResponseError

FIELDS = [
    {"name": "OBJECTID", "type": "esriFieldTypeOID"},
    {"name": "POT_MW", "type": "esriFieldTypeDouble"},
    {"name": "QTD", "type": "esriFieldTypeSmallInteger"},
    {"name": "CEG", "type": "esriFieldTypeString"},
    {"name": "DATA", "type": "esriFieldTypeDate"},
]


def write_page(
    tmp_path: Path,
    features: list[dict],
    geometry_type: str | None = "esriGeometryPoint",
    fields: list[dict] = FIELDS,
) -> Path:
    response = {
        "fields": fields,
        "features": features,
        "spatialReference": {"wkid": 4326},
    }
    if geometry_type is not None:
        response["geometryType"] = geometry_type
    path = tmp_path / "camada_0_pagina_000.json"
    path.write_text(json.dumps(response), encoding="utf-8")
    return path


def attributes(**overrides) -> dict:
    return {
        "OBJECTID": 1,
        "POT_MW": 2.0,
        "QTD": 3,
        "CEG": "EOL",
        "DATA": 1666625847000,
    } | overrides


def read(path: Path) -> pl.DataFrame:
    (chunk,) = ArcGisQueryReader().scan(path)
    return chunk.collect()


def test_dtypes_follow_the_response_fields(tmp_path):
    frame = read(
        write_page(
            tmp_path,
            [{"attributes": attributes(), "geometry": {"x": -42.6, "y": -14.5}}],
        )
    )
    assert frame.schema == pl.Schema(
        {
            "OBJECTID": pl.Int64,
            "POT_MW": pl.Float64,
            "QTD": pl.Int16,
            "CEG": pl.String,
            "DATA": pl.Datetime("ms", time_zone="UTC"),
            "geometry_x": pl.Float64,
            "geometry_y": pl.Float64,
        }
    )


def test_dates_are_epoch_milliseconds_in_utc_with_time_of_day(tmp_path):
    frame = read(write_page(tmp_path, [{"attributes": attributes()}]))
    assert frame["DATA"].to_list() == [datetime(2022, 10, 24, 15, 37, 27, tzinfo=UTC)]


def test_point_geometry_becomes_x_y_and_missing_geometry_null(tmp_path):
    features = [
        {"attributes": attributes(OBJECTID=1), "geometry": {"x": -42.6, "y": -14.5}},
        {"attributes": attributes(OBJECTID=2)},
    ]
    frame = read(write_page(tmp_path, features))
    assert frame["geometry_x"].to_list() == [-42.6, None]
    assert frame["geometry_y"].to_list() == [-14.5, None]


def test_polygon_geometry_is_kept_as_json_text(tmp_path):
    rings = {"rings": [[[-40.0, -5.0], [-40.1, -5.0], [-40.1, -5.1], [-40.0, -5.0]]]}
    frame = read(
        write_page(
            tmp_path,
            [{"attributes": attributes(), "geometry": rings}],
            "esriGeometryPolygon",
        )
    )
    assert "geometry_x" not in frame.columns
    assert json.loads(frame["geometry_json"][0]) == rings


def test_no_geometry_type_adds_no_geometry_columns(tmp_path):
    frame = read(
        write_page(tmp_path, [{"attributes": attributes()}], geometry_type=None)
    )
    assert frame.columns == [field["name"] for field in FIELDS]


def test_whole_number_in_double_field_is_accepted(tmp_path):
    # JSON writes 80.0 as 80; it is still a valid Double.
    frame = read(write_page(tmp_path, [{"attributes": attributes(POT_MW=80)}]))
    assert frame["POT_MW"].to_list() == [80.0]


def test_value_of_wrong_type_fails_instead_of_becoming_null(tmp_path):
    path = write_page(tmp_path, [{"attributes": attributes(QTD=2.5)}])
    with pytest.raises(TypeError):
        read(path)


def test_error_response_fails(tmp_path):
    path = tmp_path / "page.json"
    path.write_text(json.dumps({"error": {"code": 400, "message": "Invalid query"}}))
    with pytest.raises(ArcGisResponseError, match="Invalid query"):
        read(path)


def test_unknown_field_type_fails(tmp_path):
    fields = [{"name": "BLOB", "type": "esriFieldTypeBlob"}]
    path = write_page(tmp_path, [{"attributes": {"BLOB": "x"}}], fields=fields)
    with pytest.raises(ArcGisResponseError, match="esriFieldTypeBlob"):
        read(path)
