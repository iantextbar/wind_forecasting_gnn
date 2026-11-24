from datetime import datetime

import polars as pl
import pytest

from scripts.utils.checks import (
    SchemaMismatchError,
    TimeRange,
    check_columns,
    count_duplicate_key_rows,
    find_overlaps,
)


def test_check_columns_names_missing_and_unexpected():
    with pytest.raises(
        SchemaMismatchError,
        match=r"missing columns \['b'\], unexpected columns \['c'\]",
    ):
        check_columns(["a", "c"], ["a", "b"], context="f.parquet")


def test_check_columns_ignores_order():
    check_columns(["b", "a"], ["a", "b"], context="f.parquet")


def test_duplicate_key_rows_counts_rows_beyond_the_first():
    frame = pl.DataFrame(
        {"id": ["x", "x", "x", "y"], "t": [1, 1, 1, 1], "v": [1, 2, 3, 4]}
    )
    assert count_duplicate_key_rows(frame, ["id", "t"]) == 2


def test_duplicate_key_rows_on_empty_frame():
    assert count_duplicate_key_rows(pl.DataFrame({"id": []}), ["id"]) == 0


def hours(start: int, end: int) -> TimeRange:
    return TimeRange(datetime(2024, 1, 1, start), datetime(2024, 1, 1, end))


def test_adjacent_ranges_do_not_overlap():
    assert find_overlaps([("a", hours(0, 9)), ("b", hours(10, 19))]) == []


def test_shared_endpoint_is_an_overlap():
    assert find_overlaps([("a", hours(0, 10)), ("b", hours(10, 19))]) == [("a", "b")]


def test_long_range_overlapping_a_later_one_is_caught():
    ranges = [("long", hours(0, 20)), ("b", hours(5, 6)), ("c", hours(15, 16))]
    assert find_overlaps(ranges) == [("long", "b"), ("long", "c")]
