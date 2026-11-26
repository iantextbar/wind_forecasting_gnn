"""Resolution of every data and log location from configurable roots.

The same code runs locally (data under ``src/data``, logs under ``src/logs``) and
on Colab (``/content/...`` or Drive), so no module may hardcode a path: each takes
a ``DataPaths`` or a resolved log root.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DATA_ROOT_ENV_VAR = "WIND_GNN_DATA_ROOT"
LOG_ROOT_ENV_VAR = "WIND_GNN_LOG_ROOT"

# src/scripts/utils/paths.py -> src/. Valid for a source checkout or an editable
# install (`pip install -e .`, the Colab setup); a regular install lives in
# site-packages, so there the roots must come from the env vars.
_SRC_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_DATA_ROOT = _SRC_DIR / "data"
_DEFAULT_LOG_ROOT = _SRC_DIR / "logs"


@dataclass(frozen=True)
class DataPaths:
    """Medallion layer directories under a single data root."""

    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def bronze(self) -> Path:
        return self.root / "bronze"

    @property
    def silver(self) -> Path:
        return self.root / "silver"

    @property
    def gold(self) -> Path:
        return self.root / "gold"

    @classmethod
    def resolve(cls, root: str | Path | None = None) -> DataPaths:
        """Root: the argument, else ``$WIND_GNN_DATA_ROOT``, else ``src/data``."""
        chosen = root or os.environ.get(DATA_ROOT_ENV_VAR) or _DEFAULT_DATA_ROOT
        return cls(Path(chosen).expanduser().resolve())


def resolve_log_root(root: str | Path | None = None) -> Path:
    """Log root: the argument, else ``$WIND_GNN_LOG_ROOT``, else ``src/logs``.

    On Colab, point it at Drive: the runtime's disk is wiped when the session ends.
    """
    chosen = root or os.environ.get(LOG_ROOT_ENV_VAR) or _DEFAULT_LOG_ROOT
    return Path(chosen).expanduser().resolve()
