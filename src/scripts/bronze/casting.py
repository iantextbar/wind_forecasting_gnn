"""Casting raw columns to the declared bronze schema.

Bronze changes types, never content. Every cast is strict: a value that does not
parse fails the build instead of silently becoming null. The exceptions are the
source's declared null tokens (``TextEncoding.null_tokens``), the strings a source
writes for a missing value (ONS: ``""``; INMET: ``"-9999"`` until 2018, ``""``
after). They become null only where text becomes a typed value, and every one is
counted, so the counts are in the build metadata.

A raw file may arrive as several chunks (``RawReader``); each chunk is cast on its
own by ``cast_chunk``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import polars as pl

DOT = "."

# Float32 holds every decimal of up to 6 significant digits exactly (C's FLT_DIG):
# such a value prints back as the same decimal, so storing it as Float32 keeps the
# content. A longer value could change, so it fails the build.
FLOAT32_EXACT_DIGITS = 6
NON_DIGITS = r"[^0-9]"


class MissingFormatError(ValueError):
    """A string or integer column is cast to a date/time without a declared format."""


class FormatMatchError(ValueError):
    """No declared format, or more than one, parses a column's values."""


class TextEncodingError(ValueError):
    """A value breaks the declared encoding: wrong decimal separator, or more digits
    than the target dtype holds exactly."""


@dataclass(frozen=True)
class TextEncoding:
    """How a source writes values as text.

    Applies only where text becomes a typed value (a number, date or time); text
    columns kept as text are never changed.

    Attributes:
        null_tokens: strings that mean a missing value; each becomes null, counted.
        decimal_separator: the separator in decimal numbers (``","`` for INMET).
        formats: strptime formats for each column parsed into a date or time. When
            a column lists several (schema drift between raw files), exactly one must
            parse a chunk's values, and the whole chunk is then parsed with it.
    """

    null_tokens: tuple[str, ...] = ("",)
    decimal_separator: str = DOT
    formats: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.decimal_separator) != 1:
            raise ValueError("decimal_separator must be a single character")

        empty = sorted(name for name, options in self.formats.items() if not options)
        if empty:
            raise ValueError(f"formats lists no format for {empty}")

    def describe(self) -> dict[str, object]:
        """JSON-serialisable description, stored in the bronze metadata."""
        return {
            "null_tokens": list(self.null_tokens),
            "decimal_separator": self.decimal_separator,
            "formats": {name: list(options) for name, options in self.formats.items()},
        }


@dataclass(frozen=True)
class CastChunk:
    """One chunk cast to the target schema, and what casting did to it.

    Attributes:
        frame: the chunk with the target columns and dtypes, in target order;
            lazy, so the caller can fuse the cast with its sort. A value that
            doesn't parse raises when it is collected.
        casts: ``{column: "Source -> Target"}`` for columns whose dtype changed,
            with the format used for dates and times.
        null_tokens: ``{column: {token: count}}`` of values read as null; only
            non-zero counts.
    """

    frame: pl.LazyFrame
    casts: dict[str, str]
    null_tokens: dict[str, dict[str, int]]


def cast_chunk(
    chunk: pl.LazyFrame,
    target: Mapping[str, pl.DataType],
    encoding: TextEncoding,
    context: str,
) -> CastChunk:
    """Cast one chunk to ``target`` under the source's ``encoding``.

    The caller checks that the chunk has exactly the target's columns
    (``utils.checks.check_columns``). Encoding violations raise here (one pass over
    the chunk profiles it); a value that doesn't parse raises a Polars error when
    ``frame`` is collected.
    """
    source = chunk.collect_schema()
    profile = _profile(chunk, source, target, encoding)

    _check_encoding(profile, encoding, context)
    formats = _resolve_formats(profile, source, target, encoding, context)

    frame = chunk.select(
        # when/then names its output after the literal; keep the column's name.
        _cast_column(name, source[name], dtype, encoding, formats.get(name)).alias(name)
        for name, dtype in target.items()
    )
    return CastChunk(
        frame=frame,
        casts=describe_casts(source, target, formats),
        null_tokens=profile.null_tokens,
    )


def describe_casts(
    source: pl.Schema,
    target: Mapping[str, pl.DataType],
    formats: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Columns whose dtype changes, as ``{column: "Source -> Target"}``.

    Dates and times parsed from text name their format: ``"String -> Date
    (%Y/%m/%d)"``.
    """
    formats = formats or {}
    casts: dict[str, str] = {}
    for name, dtype in target.items():
        if source[name] == dtype:
            continue
        cast = f"{source[name]} -> {dtype}"
        casts[name] = f"{cast} ({formats[name]})" if name in formats else cast
    return casts


def text_columns(source: pl.Schema, target: Mapping[str, pl.DataType]) -> list[str]:
    """String columns cast to a non-string type: where null tokens apply."""
    return [
        name
        for name, dtype in target.items()
        if source[name] == pl.String and dtype != pl.String
    ]


@dataclass(frozen=True)
class _Profile:
    """What a chunk's text values look like, gathered in one pass before casting."""

    null_tokens: dict[str, dict[str, int]]
    foreign_separator: dict[str, int]  # values with a "." when the separator isn't
    max_digits: dict[str, int]  # significant digits, per Float32 column
    samples: dict[str, str | None]  # first value, per column with several formats


def _profile(
    chunk: pl.LazyFrame,
    source: pl.Schema,
    target: Mapping[str, pl.DataType],
    encoding: TextEncoding,
) -> _Profile:
    tokens = list(encoding.null_tokens)
    checks_separator = encoding.decimal_separator != DOT
    expressions: list[pl.Expr] = []
    labels: list[tuple[str, str, str]] = []  # (kind, column, token)

    def add(expression: pl.Expr, kind: str, column: str, token: str = "") -> None:
        expressions.append(expression.alias(f"_{len(expressions)}"))
        labels.append((kind, column, token))

    for name in text_columns(source, target):
        column, dtype = pl.col(name), target[name]
        value = pl.when(column.is_in(tokens)).then(None).otherwise(column)
        for token in tokens:
            add((column == token).sum(), "token", name, token)
        if dtype.is_numeric() and checks_separator:
            add(value.str.contains(DOT, literal=True).sum(), "separator", name)
        if dtype == pl.Float32:
            significant = (
                value.str.replace_all(NON_DIGITS, "")
                .str.strip_chars_start("0")
                .str.len_chars()
            )
            add(significant.max(), "digits", name)

    for name, dtype in target.items():
        several_formats = len(encoding.formats.get(name, ())) > 1
        if _parses_temporal(source[name], dtype) and several_formats:
            text = pl.col(name).cast(pl.String)
            if source[name] == pl.String:
                text = pl.when(text.is_in(tokens)).then(None).otherwise(text)
            add(text.drop_nulls().first(), "sample", name)

    values = chunk.select(expressions).collect().row(0) if expressions else ()

    null_tokens: dict[str, dict[str, int]] = {}
    foreign_separator: dict[str, int] = {}
    max_digits: dict[str, int] = {}
    samples: dict[str, str | None] = {}
    for (kind, column, token), value in zip(labels, values, strict=True):
        if kind == "token" and value:
            null_tokens.setdefault(column, {})[token] = value
        elif kind == "separator" and value:
            foreign_separator[column] = value
        elif kind == "digits" and value is not None:
            max_digits[column] = value
        elif kind == "sample":
            samples[column] = value

    return _Profile(null_tokens, foreign_separator, max_digits, samples)


def _check_encoding(profile: _Profile, encoding: TextEncoding, context: str) -> None:
    if profile.foreign_separator:
        raise TextEncodingError(
            f"{context}: values with '.' although the decimal separator is "
            f"{encoding.decimal_separator!r}: {profile.foreign_separator}"
        )

    too_long = {
        name: digits
        for name, digits in profile.max_digits.items()
        if digits > FLOAT32_EXACT_DIGITS
    }
    if too_long:
        raise TextEncodingError(
            f"{context}: values with more than {FLOAT32_EXACT_DIGITS} significant "
            f"digits would change as Float32: {too_long}"
        )


def _resolve_formats(
    profile: _Profile,
    source: pl.Schema,
    target: Mapping[str, pl.DataType],
    encoding: TextEncoding,
    context: str,
) -> dict[str, str]:
    """The one format each date/time column of this chunk is parsed with.

    With several candidates, the format is chosen from the chunk's first value and
    then applied strictly to every value, so a chunk that mixes formats fails
    instead of being parsed value by value with whichever format happens to match.
    """
    formats: dict[str, str] = {}
    for name, dtype in target.items():
        if not _parses_temporal(source[name], dtype):
            continue

        options = encoding.formats.get(name)
        if not options:
            raise MissingFormatError(
                f"{context}: column {name!r}: casting {source[name]} to {dtype} "
                "needs a format"
            )

        sample = profile.samples.get(name)
        if len(options) == 1 or sample is None:
            formats[name] = options[0]
            continue

        matching = [fmt for fmt in options if _parses(sample, dtype, fmt)]
        if len(matching) != 1:
            raise FormatMatchError(
                f"{context}: column {name!r}: value {sample!r} matches "
                f"{len(matching)} of the formats {list(options)}; exactly one must"
            )
        formats[name] = matching[0]

    return formats


def _parses(value: str, dtype: pl.DataType, fmt: str) -> bool:
    try:
        pl.Series([value]).str.strptime(dtype, fmt, strict=True)
    except pl.exceptions.PolarsError:
        return False
    return True


def _parses_temporal(source: pl.DataType, target: pl.DataType) -> bool:
    return target.is_temporal() and (source == pl.String or source.is_integer())


def _cast_column(
    name: str,
    source: pl.DataType,
    target: pl.DataType,
    encoding: TextEncoding,
    fmt: str | None,
) -> pl.Expr:
    column = pl.col(name)
    if source == target:
        return column

    if _parses_temporal(source, target):
        if source == pl.String:
            text = _tokens_to_null(column, encoding)
        else:
            # Integer dates (e.g. 20250531) are parsed through their decimal digits.
            text = column.cast(pl.String)
        return text.str.strptime(target, fmt, strict=True)

    if source == pl.String:
        text = _tokens_to_null(column, encoding)
        if target.is_numeric() and encoding.decimal_separator != DOT:
            text = text.str.replace(encoding.decimal_separator, DOT, literal=True)
        return text.cast(target, strict=True)

    return column.cast(target, strict=True)


def _tokens_to_null(column: pl.Expr, encoding: TextEncoding) -> pl.Expr:
    return (
        pl.when(column.is_in(list(encoding.null_tokens))).then(None).otherwise(column)
    )
