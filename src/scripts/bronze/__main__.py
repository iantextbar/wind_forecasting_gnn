"""Command line: ``uv run python -m scripts.bronze [--source NAME ...] [--force]``.

``--save-log`` also writes the run's log to ``src/logs/data/bronze/`` (or under
``$WIND_GNN_LOG_ROOT``).
"""

from __future__ import annotations

import argparse
import logging

from scripts.bronze.build import build_all
from scripts.bronze.specs import SOURCES
from scripts.utils.log import new_log_file, setup_logging
from scripts.utils.paths import DATA_ROOT_ENV_VAR, DataPaths, resolve_log_root

LOG_STEP = "data/bronze"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build the bronze layer from raw files."
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(SOURCES),
        help="source to build; repeatable (default: all)",
    )
    parser.add_argument(
        "--force", action="store_true", help="rebuild even if up to date"
    )
    parser.add_argument(
        "--data-root", help=f"data root (default: ${DATA_ROOT_ENV_VAR}, else src/data)"
    )
    parser.add_argument("--verbose", action="store_true", help="log every raw file")
    parser.add_argument(
        "--save-log",
        action="store_true",
        help=f"also save the full log (DEBUG) under <log root>/{LOG_STEP}/",
    )
    args = parser.parse_args(argv)

    log_root = resolve_log_root()
    log_file = new_log_file(log_root, LOG_STEP) if args.save_log else None
    setup_logging(logging.DEBUG if args.verbose else logging.INFO, log_file)

    logger = logging.getLogger(__name__)
    paths = DataPaths.resolve(args.data_root)
    logger.info("data root: %s", paths.root)
    if log_file is not None:
        logger.info("saving log to %s", log_file)

    run_log = log_file.relative_to(log_root).as_posix() if log_file else None
    build_all(SOURCES, paths, args.source, force=args.force, run_log=run_log)


if __name__ == "__main__":
    main()
