"""Configuration and on-disk locations.

The data directory is resolved with a clear precedence so the library behaves the same
whether run from a source checkout, an installed wheel, the TUI, the CLI, or an embedding
app:

1. ``$JARS_DATA_DIR`` — explicit override, always wins.
2. The source-tree ``data/`` directory — used when running from an editable checkout, so
   the bundled offline database ships alongside the code.
3. A writable per-user data directory (``platformdirs.user_data_dir("jars")``) — the
   fallback for an installed wheel, where the source layout no longer exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_DATA_DIR = "JARS_DATA_DIR"

# The source-tree data directory: <project root>/data. This file lives at
# <project root>/src/jars_lib/config.py, so the project root is two parents up. When the
# package is installed as a wheel this path points inside site-packages and won't exist,
# so we only use it when present (see data_dir()).
PROJECT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# File names within the data directory.
CUTOFFS_FILE = "cutoffs.parquet"
NIRF_FILE = "nirf_engineering.json"
META_FILE = "meta.json"
NAME_MAP_FILE = "name_map.json"

# Fuzzy-match acceptance threshold (rapidfuzz token_sort_ratio, 0..100).
DEFAULT_NAME_MATCH_THRESHOLD = 88.0


def _user_data_dir() -> Path:
    """A writable per-user data directory for installed (non-editable) use.

    Prefers ``platformdirs`` for correct per-OS locations; falls back to a hand-rolled
    ``~/.local/share/jars`` (XDG-style) path so the library still works if the optional
    dependency is missing.
    """
    try:
        from platformdirs import user_data_dir

        return Path(user_data_dir("jars"))
    except Exception:  # pragma: no cover - exercised only without platformdirs
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
        return Path(base) / "jars"


def data_dir() -> Path:
    """Resolve the data directory.

    Precedence: ``$JARS_DATA_DIR`` → source-tree ``data/`` (if it exists) → per-user data
    directory. The source path is skipped when absent (e.g. an installed wheel) so the
    library never points at a non-existent location inside site-packages.
    """
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override)
    if PROJECT_DATA_DIR.exists():
        return PROJECT_DATA_DIR
    return _user_data_dir()


@dataclass(slots=True)
class Paths:
    """Resolved file paths derived from the data directory."""

    root: Path

    @classmethod
    def resolve(cls) -> "Paths":
        return cls(root=data_dir())

    @property
    def cutoffs(self) -> Path:
        return self.root / CUTOFFS_FILE

    @property
    def nirf(self) -> Path:
        return self.root / NIRF_FILE

    @property
    def meta(self) -> Path:
        return self.root / META_FILE

    @property
    def name_map(self) -> Path:
        return self.root / NAME_MAP_FILE

    def ensure(self) -> "Paths":
        self.root.mkdir(parents=True, exist_ok=True)
        return self
