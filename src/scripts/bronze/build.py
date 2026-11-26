"""Bronze build: the raw files of one source become typed, checked, sorted parts.

Layout of ``bronze/<source>/`` (D-028):
- ``part-NNNNN.parquet``: one part per raw file, numbered in time order, each
  sorted by the spec's sort keys. Read the whole source with
  ``pl.scan_parquet("bronze/<source>/*.parquet")``.
- ``_bronze_meta.json``: provenance and per-file reports.

One raw file is processed at a time, so peak memory is one file, not the source.
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import shutil
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import polars as pl

from scripts.bronze.casting import (
    blank_columns,
    cast_expressions,
    count_empty_strings,
    describe_casts,
)
from scripts.bronze.specs import SourceSpec
from scripts.utils.checks import (
    OverlapError,
    TimeRange,
    check_columns,
    count_duplicate_key_rows,
    find_overlaps,
)
from scripts.utils.paths import DataPaths
from scripts.utils.provenance import git_commit, sha256_file

logger = logging.getLogger(__name__)

META_FILENAME = "_bronze_meta.json"
PART_NAME_TEMPLATE = "part-{index:05d}.parquet"
PARQUET_COMPRESSION = "zstd"

# Hidden files (.gitkeep) are placeholders, never data.
HIDDEN_PREFIX = "."


class BronzeBuildError(RuntimeError):
    """A source could not be built; the existing bronze output is left untouched."""


@dataclass(frozen=True)
class FileReport:
    """What happened to one raw file. ``rows`` counts are never reduced in bronze."""

    raw_file: str
    sha256: str
    raw_modified_utc: str
    rows: int
    casts: dict[str, str]
    empty_strings_to_null: dict[str, int]
    duplicate_key_rows: int
    time_range: TimeRange | None
    time_nulls: int


@dataclass(frozen=True)
class BronzeReport:
    """Summary of one source's build."""

    source: str
    status: Literal["built", "skipped"]
    output_dir: Path
    parts: int
    rows: int
    duplicate_key_rows: int


def find_raw_files(spec: SourceSpec, raw_root: Path) -> list[Path]:
    """Raw files of a source, sorted by name."""
    folder = raw_root / spec.raw_path
    if not folder.is_dir():
        raise FileNotFoundError(f"{spec.name}: raw folder {folder} does not exist")

    matched = sorted(
        {path for pattern in spec.patterns for path in folder.glob(pattern)}
    )
    if not matched:
        raise FileNotFoundError(
            f"{spec.name}: no file in {folder} matches {spec.patterns}"
        )

    return matched


def unclaimed_raw_files(
    specs: Iterable[SourceSpec], raw_root: Path
) -> dict[str, list[str]]:
    """Files in the specs' raw folders that no spec reads or expects as a companion.

    Checked across all specs at once because several sources can share a folder
    (one SIGEL snapshot holds three): a file is unclaimed only if no spec claims it.
    Returns ``{raw folder: [file names]}`` for folders with unclaimed files.
    """
    claims: dict[str, set[str]] = {}
    for spec in specs:
        patterns = (*spec.patterns, *spec.companions)
        claims.setdefault(spec.raw_path, set()).update(patterns)

    unclaimed: dict[str, list[str]] = {}
    for raw_path, patterns in claims.items():
        folder = raw_root / raw_path
        if not folder.is_dir():
            continue

        claimed = {path for pattern in patterns for path in folder.glob(pattern)}
        names = sorted(
            path.name
            for path in folder.iterdir()
            if path.is_file()
            and path not in claimed
            and not path.name.startswith(HIDDEN_PREFIX)
        )
        if names:
            unclaimed[raw_path] = names

    return unclaimed


def build_bronze(
    spec: SourceSpec,
    paths: DataPaths,
    *,
    force: bool = False,
    run_log: str | None = None,
) -> BronzeReport:
    """Build ``bronze/<spec.name>/`` from the spec's raw folder.

    Skipped when the existing output was built from the same spec and the same raw
    file hashes, unless ``force``. Code changes are not detected: pass ``force``
    after changing the casting or build logic. ``run_log`` names the saved log
    file of this run, if any; it is recorded in the metadata.
    """
    raw_files = find_raw_files(spec, paths.raw)
    logger.info("%s: hashing %d raw file(s)", spec.name, len(raw_files))
    hashes = {path.name: sha256_file(path) for path in raw_files}
    fingerprint = _fingerprint(spec, hashes)
    output_dir = paths.bronze / spec.name

    existing = _read_metadata(output_dir)
    if not force and existing is not None and existing["fingerprint"] == fingerprint:
        logger.info("%s: up to date, skipped", spec.name)
        return BronzeReport(
            source=spec.name,
            status="skipped",
            output_dir=output_dir,
            parts=len(existing["parts"]),
            rows=existing["rows"],
            duplicate_key_rows=existing["duplicate_key_rows"],
        )

    staging = paths.bronze / f".{spec.name}.staging"
    shutil.rmtree(staging, ignore_errors=True)  # leftover of an interrupted build
    staging.mkdir(parents=True)

    try:
        reports = [
            _ingest_file(
                spec, path, hashes[path.name], staging, position, len(raw_files)
            )
            for position, path in enumerate(raw_files, start=1)
        ]

        ordered = _order_by_time(spec, reports)
        _rename_to_parts(staging, ordered)

        duplicates = _source_duplicate_key_rows(spec, staging, ordered)
        metadata = _metadata(spec, fingerprint, ordered, duplicates, run_log)
        meta_text = json.dumps(metadata, indent=2, ensure_ascii=False)
        (staging / META_FILENAME).write_text(meta_text)

        _swap_into_place(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    report = BronzeReport(
        source=spec.name,
        status="built",
        output_dir=output_dir,
        parts=len(ordered),
        rows=metadata["rows"],
        duplicate_key_rows=metadata["duplicate_key_rows"],
    )
    _log_summary(report, metadata)
    return report


def build_all(
    specs: Mapping[str, SourceSpec],
    paths: DataPaths,
    names: Iterable[str] | None = None,
    *,
    force: bool = False,
    run_log: str | None = None,
) -> list[BronzeReport]:
    """Build the selected sources one after another (D-028: sequential by design).

    Sources are independent, so a failure is logged and the remaining sources are
    still built; the call then raises listing every failed source.
    """
    selected = list(specs) if names is None else list(names)
    if unknown := sorted(set(selected) - set(specs)):
        raise ValueError(f"unknown sources {unknown}; known: {sorted(specs)}")

    selected_folders = {specs[name].raw_path for name in selected}
    for raw_path, files in unclaimed_raw_files(specs.values(), paths.raw).items():
        if raw_path in selected_folders:
            logger.warning(
                "raw/%s: %d file(s) no source reads: %s", raw_path, len(files), files
            )

    reports: list[BronzeReport] = []
    failed: list[str] = []
    for name in selected:
        try:
            report = build_bronze(specs[name], paths, force=force, run_log=run_log)
            reports.append(report)
        except Exception:
            logger.exception(
                "%s: bronze build failed; previous output left untouched", name
            )
            failed.append(name)

    if failed:
        raise BronzeBuildError(f"bronze build failed for {failed}")
    return reports


def _ingest_file(
    spec: SourceSpec, path: Path, sha256: str, staging: Path, position: int, total: int
) -> FileReport:
    context = f"{spec.name}/{path.name}"
    lazy = spec.reader.scan(path)
    source_schema = lazy.collect_schema()
    check_columns(source_schema.names(), spec.schema, context=context)

    empties = count_empty_strings(lazy, blank_columns(source_schema, spec.schema))
    try:
        frame = (
            lazy.select(cast_expressions(source_schema, spec.schema, spec.formats))
            # Stable sort: rows with equal keys keep their raw order, so the
            # output is identical on every run (D-011).
            .sort(spec.sort_keys, maintain_order=True)
            .collect()
        )
    except pl.exceptions.PolarsError as error:
        raise BronzeBuildError(f"{context}: {error}") from error

    time_range, time_nulls = _time_summary(frame, spec.time_column)
    duplicates = count_duplicate_key_rows(frame, spec.unique_keys)

    part_path = staging / f"{path.stem}.parquet"
    frame.write_parquet(part_path, compression=PARQUET_COMPRESSION)
    logger.debug(
        "%s: [%d/%d] %d rows, %d duplicate-key rows, empty strings to null %s",
        context,
        position,
        total,
        frame.height,
        duplicates,
        empties,
    )

    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return FileReport(
        raw_file=path.name,
        sha256=sha256,
        raw_modified_utc=modified.isoformat(timespec="seconds"),
        rows=frame.height,
        casts=describe_casts(source_schema, spec.schema),
        empty_strings_to_null=empties,
        duplicate_key_rows=duplicates,
        time_range=time_range,
        time_nulls=time_nulls,
    )


def _time_summary(
    frame: pl.DataFrame, time_column: str | None
) -> tuple[TimeRange | None, int]:
    if time_column is None:
        return None, 0

    column = frame[time_column]
    nulls = column.null_count()
    if nulls == frame.height:
        return None, nulls

    return TimeRange(start=column.min(), end=column.max()), nulls


def _order_by_time(spec: SourceSpec, reports: list[FileReport]) -> list[FileReport]:
    """Order files by the start of their time range; ranges must not overlap.

    File names don't give time order (``FATOR_CAPACIDADE-2_2022_01`` sorts before
    ``FATOR_CAPACIDADE_2009``), so the order comes from the data. Non-overlapping
    ranges are what make the concatenated parts globally sorted.
    """
    if spec.time_column is None:
        return reports

    # Files with no timestamped rows cannot break the order; keep them first, by name.
    untimed = [report for report in reports if report.time_range is None]
    timed = sorted(
        (report for report in reports if report.time_range is not None),
        key=lambda report: (report.time_range.start, report.raw_file),
    )

    overlaps = find_overlaps([(report.raw_file, report.time_range) for report in timed])
    if overlaps:
        raise OverlapError(
            f"{spec.name}: raw files with overlapping {spec.time_column} "
            f"ranges: {overlaps}"
        )

    return untimed + timed


def _source_duplicate_key_rows(
    spec: SourceSpec, staging: Path, ordered: list[FileReport]
) -> int:
    """Duplicate-key rows over the whole source.

    With a time column, keys include it and parts never share an instant
    (``_order_by_time``), so per-part counts add up. Without one (static
    registries split into pages), a key can repeat across pages, so the parts
    are counted together; these sources are small.
    """
    if spec.time_column is not None or len(ordered) == 1:
        return sum(report.duplicate_key_rows for report in ordered)

    keys = pl.scan_parquet(staging / "*.parquet").select(spec.unique_keys).collect()
    return count_duplicate_key_rows(keys, spec.unique_keys)


def _rename_to_parts(staging: Path, ordered: list[FileReport]) -> None:
    for index, report in enumerate(ordered):
        staged = staging / f"{Path(report.raw_file).stem}.parquet"
        staged.rename(staging / PART_NAME_TEMPLATE.format(index=index))


def _swap_into_place(staging: Path, target: Path) -> None:
    """Replace ``target`` with the complete staging directory.

    Readers never see a half-written source: the old output stays in place until
    the new one is complete, and is removed only after the swap.
    """
    retired = target.with_name(f".{target.name}.retired")
    shutil.rmtree(retired, ignore_errors=True)

    if target.exists():
        target.rename(retired)
    staging.rename(target)

    shutil.rmtree(retired, ignore_errors=True)


def _fingerprint(spec: SourceSpec, hashes: Mapping[str, str]) -> str:
    inputs = dict(sorted(hashes.items()))
    payload = json.dumps({"spec": spec.fingerprint(), "inputs": inputs})
    return hashlib.sha256(payload.encode()).hexdigest()


def _read_metadata(output_dir: Path) -> dict | None:
    meta_path = output_dir / META_FILENAME
    if not meta_path.is_file():
        return None
    return json.loads(meta_path.read_text())


def _metadata(
    spec: SourceSpec,
    fingerprint: str,
    ordered: list[FileReport],
    duplicates: int,
    run_log: str | None,
) -> dict:
    empties: Counter[str] = Counter()
    for report in ordered:
        empties.update(report.empty_strings_to_null)

    return {
        "source": spec.name,
        "built_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "fingerprint": fingerprint,
        "git_commit": git_commit(),
        "run_log": run_log,
        "polars_version": pl.__version__,
        "python_version": platform.python_version(),
        "spec": spec.describe(),
        "rows": sum(report.rows for report in ordered),
        "duplicate_key_rows": duplicates,
        "empty_strings_to_null": dict(sorted(empties.items())),
        "parts": [
            _part_metadata(index, report) for index, report in enumerate(ordered)
        ],
    }


def _part_metadata(index: int, report: FileReport) -> dict:
    time_range = report.time_range
    return {
        "part": PART_NAME_TEMPLATE.format(index=index),
        "raw_file": report.raw_file,
        "sha256": report.sha256,
        "raw_modified_utc": report.raw_modified_utc,
        "rows": report.rows,
        "casts": report.casts,
        "empty_strings_to_null": report.empty_strings_to_null,
        "duplicate_key_rows": report.duplicate_key_rows,
        "time_start": time_range.start.isoformat() if time_range else None,
        "time_end": time_range.end.isoformat() if time_range else None,
        "time_nulls": report.time_nulls,
    }


def _log_summary(report: BronzeReport, metadata: dict) -> None:
    logger.info(
        "%s: built %d part(s), %d rows (no rows dropped in bronze)",
        report.source,
        report.parts,
        report.rows,
    )

    if metadata["empty_strings_to_null"]:
        logger.info(
            "%s: empty strings read as null: %s",
            report.source,
            metadata["empty_strings_to_null"],
        )

    if report.duplicate_key_rows:
        logger.warning(
            "%s: %d rows repeat a key %s; kept, for silver to resolve",
            report.source,
            report.duplicate_key_rows,
            metadata["spec"]["unique_keys"],
        )

    time_nulls = sum(part["time_nulls"] for part in metadata["parts"])
    if time_nulls:
        logger.warning("%s: %d rows have a null time column", report.source, time_nulls)
