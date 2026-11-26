from datetime import date, time

import polars as pl
import pytest

from scripts.bronze.casting import (
    MissingFormatError,
    blank_columns,
    cast_expressions,
    count_empty_strings,
    describe_casts,
)


def cast(
    frame: pl.DataFrame, target: dict, formats: dict | None = None
) -> pl.DataFrame:
    return frame.select(cast_expressions(frame.schema, target, formats or {}))


def test_ons_decimal_strings_parse_including_scientific_zero():
    frame = pl.DataFrame({"val": ["101.35300000", "0E-8", "0E-20"]})
    assert cast(frame, {"val": pl.Float64})["val"].to_list() == [101.353, 0.0, 0.0]


def test_empty_string_becomes_null_and_is_counted():
    frame = pl.DataFrame({"val": ["1.5", "", None]})
    target = {"val": pl.Float64}
    assert cast(frame, target)["val"].to_list() == [1.5, None, None]
    columns = blank_columns(frame.schema, target)
    assert count_empty_strings(frame.lazy(), columns) == {"val": 1}


def test_unparseable_number_fails_instead_of_becoming_null():
    frame = pl.DataFrame({"val": ["1.5", "n/a"]})
    with pytest.raises(pl.exceptions.InvalidOperationError):
        cast(frame, {"val": pl.Float64})


def test_compact_date_parses_from_string_and_from_integer():
    # One previsao file stores dat_programacao as Int64 instead of "YYYYMMDD".
    target, formats = {"d": pl.Date}, {"d": "%Y%m%d"}
    from_text = cast(pl.DataFrame({"d": ["20250531"]}), target, formats)
    from_int = cast(pl.DataFrame({"d": [20250531]}), target, formats)
    assert from_text["d"].to_list() == from_int["d"].to_list() == [date(2025, 5, 31)]


def test_clock_time_parses():
    frame = pl.DataFrame({"t": ["23:59:00"]})
    assert cast(frame, {"t": pl.Time}, {"t": "%H:%M:%S"})["t"].to_list() == [
        time(23, 59)
    ]


def test_temporal_cast_without_format_is_rejected():
    with pytest.raises(MissingFormatError):
        cast(pl.DataFrame({"d": ["2025-05-31"]}), {"d": pl.Date})


def test_integer_narrowing_overflow_fails():
    frame = pl.DataFrame({"n": [2**40]})
    with pytest.raises(pl.exceptions.InvalidOperationError):
        cast(frame, {"n": pl.Int32})


def test_unchanged_columns_are_not_reported_as_casts():
    frame = pl.DataFrame({"a": ["x"], "b": ["1.0"]})
    assert describe_casts(frame.schema, {"a": pl.String, "b": pl.Float64}) == {
        "b": "String -> Float64"
    }


def test_output_follows_target_column_order():
    frame = pl.DataFrame({"b": [1.0], "a": ["x"]})
    assert cast(frame, {"a": pl.String, "b": pl.Float64}).columns == ["a", "b"]
