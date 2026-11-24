"""Casting raw columns to the declared bronze schema.

Bronze changes types, never content. Every cast is strict: a value that does not
parse fails the build instead of silently becoming null. The single exception is
the empty string, which ONS writes for a missing number in its decimal-string
columns; it becomes null and is counted, so the count is in the build metadata.
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

EMPTY_STRING = ""


class MissingFormatError(ValueError):
    """A string or integer column is cast to a date/time without a declared format."""


def describe_casts(
    source: pl.Schema, target: Mapping[str, pl.DataType]
) -> dict[str, str]:
    """Columns whose dtype changes, as ``{column: "Source -> Target"}``."""
    return {
        name: f"{source[name]} -> {dtype}"
        for name, dtype in target.items()
        if source[name] != dtype
    }


def blank_columns(source: pl.Schema, target: Mapping[str, pl.DataType]) -> list[str]:
    """String columns cast to a non-string type, where an empty string means missing."""
    return [
        name
        for name, dtype in target.items()
        if source[name] == pl.String and dtype != pl.String
    ]


def count_empty_strings(frame: pl.LazyFrame, columns: list[str]) -> dict[str, int]:
    """Number of empty strings per column; only non-zero counts are returned."""
    if not columns:
        return {}

    counts = frame.select(
        (pl.col(name) == EMPTY_STRING).sum().alias(name) for name in columns
    ).collect()
    return {name: count for name, count in counts.row(0, named=True).items() if count}


def cast_expressions(
    source: pl.Schema,
    target: Mapping[str, pl.DataType],
    formats: Mapping[str, str],
) -> list[pl.Expr]:
    """One expression per target column, in target order.

    The caller is responsible for checking that source and target have the same
    columns (``utils.checks.check_columns``).
    """
    return [
        _cast_column(name, source[name], dtype, formats.get(name))
        for name, dtype in target.items()
    ]


def _cast_column(
    name: str, source: pl.DataType, target: pl.DataType, fmt: str | None
) -> pl.Expr:
    column = pl.col(name)
    if source == target:
        return column

    if target.is_temporal() and (source == pl.String or source.is_integer()):
        if fmt is None:
            raise MissingFormatError(
                f"column {name!r}: casting {source} to {target} needs a format"
            )

        # Integer dates (e.g. 20250531) are parsed through their decimal digits.
        as_text = column if source == pl.String else column.cast(pl.String)
        return _empty_to_null(as_text).str.strptime(target, fmt, strict=True)

    if source == pl.String:
        return _empty_to_null(column).cast(target, strict=True)

    return column.cast(target, strict=True)


def _empty_to_null(column: pl.Expr) -> pl.Expr:
    return column.replace(EMPTY_STRING, None)
