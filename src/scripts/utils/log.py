"""Logger configuration shared by every pipeline and training entry point.

Logs always go to the terminal. Saving them to a file is optional, for costly
steps (full rebuilds, training) whose record should outlive the session:
``<log root>/<step>/<UTC timestamp>.log``, with steps such as ``data/bronze``,
``data/silver`` or ``model/DCRNN``.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
# UTC everywhere, like the log file names, so log lines from a local run and a
# Colab run compare directly.
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
FILE_TIMESTAMP = "%Y%m%dT%H%M%SZ"


def new_log_file(log_root: Path, step: str, now: datetime | None = None) -> Path:
    """Path of a new log file: ``<log_root>/<step>/<UTC timestamp>.log``.

    ``step`` is a relative path naming the pipeline step, e.g. ``data/bronze``.
    """
    step_path = PurePosixPath(step)
    if not step_path.parts or step_path.is_absolute() or ".." in step_path.parts:
        raise ValueError(f"step must be a relative path like 'data/bronze': {step!r}")

    stamp = (now or datetime.now(UTC)).strftime(FILE_TIMESTAMP)
    return log_root.joinpath(*step_path.parts) / f"{stamp}.log"


def setup_logging(level: int = logging.INFO, log_file: Path | None = None) -> None:
    """Configure the root logger, for entry points only.

    The terminal shows ``level`` and above. A log file, when given, records
    everything down to DEBUG, so it is the complete record of the run. Library
    modules never call this; they just use ``logging.getLogger(__name__)``.
    """
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    formatter.converter = time.gmtime

    console = logging.StreamHandler()
    console.setLevel(level)
    handlers: list[logging.Handler] = [console]

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        handlers.append(file_handler)

    for handler in handlers:
        handler.setFormatter(formatter)

    root_level = logging.DEBUG if log_file is not None else level
    logging.basicConfig(level=root_level, handlers=handlers, force=True)
