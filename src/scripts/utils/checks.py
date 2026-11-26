"""Data checks used at layer boundaries.

Each function either raises on a structural violation (the layer's guarantees would
break) or returns a count for the caller to report (data quality, decided downstream).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import polars as pl

Instant = date | datetime


class SchemaMismatchError(ValueError):
    """A file's columns differ from the declared schema."""


class OverlapError(ValueError):
    """Two partitions cover overlapping time ranges."""


def check_columns(actual: Iterable[str], expected: Iterable[str], context: str) -> None:
    """Raise if columns are missing or unexpected. Column order is not checked."""
    actual_set, expected_set = set(actual), set(expected)
    missing = sorted(expected_set - actual_set)
    unexpected = sorted(actual_set - expected_set)

    if missing or unexpected:
        raise SchemaMismatchError(
            f"{context}: missing columns {missing}, unexpected columns {unexpected}"
        )


def count_duplicate_key_rows(frame: pl.DataFrame, keys: Sequence[str]) -> int:
    """Rows beyond the first for each key: how many rows a keep-one dedup would drop."""
    if frame.is_empty():
        return 0
    return frame.height - frame.select(keys).n_unique()


@dataclass(frozen=True)
class TimeRange:
    """Closed interval [start, end] of a partition's time column."""

    start: Instant
    end: Instant


def find_overlaps(ranges: Sequence[tuple[str, TimeRange]]) -> list[tuple[str, str]]:
    """Pairs of labelled ranges that overlap, given ranges sorted by start.

    Compares each range with the latest end seen so far, so a long range that
    covers several later ones is caught, not only adjacent pairs.
    """
    overlaps: list[tuple[str, str]] = []
    furthest: tuple[str, TimeRange] | None = None

    for label, current in ranges:
        if furthest is not None and current.start <= furthest[1].end:
            overlaps.append((furthest[0], label))
        if furthest is None or current.end > furthest[1].end:
            furthest = (label, current)

    return overlaps
