from dataclasses import replace
from datetime import date, time

import polars as pl
import pytest

from scripts.bronze.casting import (
    CastChunk,
    FormatMatchError,
    MissingFormatError,
    TextEncoding,
    TextEncodingError,
    cast_chunk,
    describe_casts,
)

# INMET-like encoding: decimal commas, two missing-value spellings, two date spellings.
INMET_LIKE = TextEncoding(
    null_tokens=("", "-9999"),
    decimal_separator=",",
    formats={"d": ("%Y-%m-%d", "%Y/%m/%d")},
)


def cast(
    frame: pl.DataFrame, target: dict, encoding: TextEncoding | None = None
) -> CastChunk:
    """Cast and collect, so parse errors raise here as they do in the build."""
    result = cast_chunk(frame.lazy(), target, encoding or TextEncoding(), "test")
    return replace(result, frame=result.frame.collect())


def test_ons_decimal_strings_parse_including_scientific_zero():
    frame = pl.DataFrame({"val": ["101.35300000", "0E-8", "0E-20"]})
    result = cast(frame, {"val": pl.Float64})
    assert result.frame["val"].to_list() == [101.353, 0.0, 0.0]


def test_empty_string_becomes_null_and_is_counted():
    frame = pl.DataFrame({"val": ["1.5", "", None]})
    result = cast(frame, {"val": pl.Float64})
    assert result.frame["val"].to_list() == [1.5, None, None]
    assert result.null_tokens == {"val": {"": 1}}


def test_declared_null_tokens_become_null_and_are_counted_per_token():
    frame = pl.DataFrame({"val": ["1,5", "-9999", "", "-9999"]})
    result = cast(frame, {"val": pl.Float32}, INMET_LIKE)
    assert result.frame["val"].to_list() == [1.5, None, None, None]
    assert result.null_tokens == {"val": {"": 1, "-9999": 2}}


def test_null_tokens_leave_text_columns_untouched():
    frame = pl.DataFrame({"code": ["-9999", ""], "val": ["1", "2"]})
    result = cast(frame, {"code": pl.String, "val": pl.Float32}, INMET_LIKE)
    assert result.frame["code"].to_list() == ["-9999", ""]
    assert result.null_tokens == {}


def test_a_token_that_is_not_declared_is_a_value():
    # ONS's default encoding knows only "": -9999 there stays a number.
    result = cast(pl.DataFrame({"val": ["-9999"]}), {"val": pl.Float64})
    assert result.frame["val"].to_list() == [-9999.0]


def test_decimal_comma_parses_without_leading_zero():
    frame = pl.DataFrame({"val": [",8", "-,5", "885,4"]})
    result = cast(frame, {"val": pl.Float32}, INMET_LIKE)
    assert [str(v) for v in result.frame["val"].cast(pl.String)] == [
        "0.8",
        "-0.5",
        "885.4",
    ]


def test_a_dot_under_a_comma_encoding_fails():
    frame = pl.DataFrame({"val": ["1,5", "1.5"]})
    with pytest.raises(TextEncodingError, match="decimal separator"):
        cast(frame, {"val": pl.Float32}, INMET_LIKE)


def test_float32_rejects_values_it_cannot_hold_exactly():
    exact = pl.DataFrame({"val": ["1234,5", "0,000123"]})
    assert cast(exact, {"val": pl.Float32}, INMET_LIKE).frame.height == 2

    too_long = pl.DataFrame({"val": ["1234,567"]})
    with pytest.raises(TextEncodingError, match="significant digits"):
        cast(too_long, {"val": pl.Float32}, INMET_LIKE)


def test_one_of_several_formats_is_chosen_per_chunk_and_recorded():
    old = cast(pl.DataFrame({"d": ["2009-01-01", ""]}), {"d": pl.Date}, INMET_LIKE)
    new = cast(pl.DataFrame({"d": ["-9999", "2019/01/01"]}), {"d": pl.Date}, INMET_LIKE)
    assert old.frame["d"].to_list() == [date(2009, 1, 1), None]
    assert new.frame["d"].to_list() == [None, date(2019, 1, 1)]
    assert old.casts == {"d": "String -> Date (%Y-%m-%d)"}
    assert new.casts == {"d": "String -> Date (%Y/%m/%d)"}


def test_a_chunk_mixing_formats_fails():
    frame = pl.DataFrame({"d": ["2009-01-01", "2019/01/01"]})
    with pytest.raises(pl.exceptions.InvalidOperationError):
        cast(frame, {"d": pl.Date}, INMET_LIKE)


def test_a_value_no_format_parses_fails():
    with pytest.raises(FormatMatchError, match="0 of the formats"):
        cast(pl.DataFrame({"d": ["01.01.2009"]}), {"d": pl.Date}, INMET_LIKE)


def test_ambiguous_formats_fail():
    ambiguous = TextEncoding(formats={"d": ("%d/%m/%Y", "%m/%d/%Y")})
    with pytest.raises(FormatMatchError, match="2 of the formats"):
        cast(pl.DataFrame({"d": ["01/02/2020"]}), {"d": pl.Date}, ambiguous)


def test_compact_date_parses_from_string_and_from_integer():
    # One previsao file stores dat_programacao as Int64 instead of "YYYYMMDD".
    target = {"d": pl.Date}
    encoding = TextEncoding(formats={"d": ("%Y%m%d",)})
    from_text = cast(pl.DataFrame({"d": ["20250531"]}), target, encoding)
    from_int = cast(pl.DataFrame({"d": [20250531]}), target, encoding)
    assert from_text.frame["d"].to_list() == [date(2025, 5, 31)]
    assert from_int.frame["d"].to_list() == [date(2025, 5, 31)]


def test_clock_times_parse_in_both_inmet_spellings():
    encoding = TextEncoding(formats={"t": ("%H:%M", "%H%M UTC")})
    old = cast(pl.DataFrame({"t": ["23:00"]}), {"t": pl.Time}, encoding)
    new = cast(pl.DataFrame({"t": ["2300 UTC"]}), {"t": pl.Time}, encoding)
    assert old.frame["t"].to_list() == new.frame["t"].to_list() == [time(23)]


def test_temporal_cast_without_format_is_rejected():
    with pytest.raises(MissingFormatError):
        cast(pl.DataFrame({"d": ["2025-05-31"]}), {"d": pl.Date})


def test_unparseable_number_fails_instead_of_becoming_null():
    frame = pl.DataFrame({"val": ["1.5", "n/a"]})
    with pytest.raises(pl.exceptions.InvalidOperationError):
        cast(frame, {"val": pl.Float64})


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
    result = cast(frame, {"a": pl.String, "b": pl.Float64})
    assert result.frame.columns == ["a", "b"]


def test_encoding_rejects_a_column_with_no_format():
    with pytest.raises(ValueError, match="no format"):
        TextEncoding(formats={"d": ()})
