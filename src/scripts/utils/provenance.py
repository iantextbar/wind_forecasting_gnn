"""Facts recorded with every derived artifact, tracing it to its inputs and code."""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_HASH_CHUNK_BYTES = 1 << 20
_REPO_DIR = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file, read in chunks so memory stays constant."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)

    return digest.hexdigest()


def git_commit() -> str | None:
    """Current commit hash, suffixed ``-dirty`` if tracked files have changes.

    A dirty suffix matters: the output was produced by code that no commit records.
    Returns None outside a git checkout.
    """
    try:
        commit = _git("rev-parse", "HEAD")
        dirty = _git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.CalledProcessError):
        logger.warning("git commit unavailable; artifact provenance will lack it")
        return None

    return f"{commit}-dirty" if dirty else commit


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=_REPO_DIR, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()
