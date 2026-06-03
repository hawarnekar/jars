"""Configuration and on-disk locations.

Data lives in the project's ``data/`` directory (overridable with JARS_DATA_DIR) so the
offline database ships alongside the code and the library behaves the same whether driven
by the TUI, the CLI, or an embedding app.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_DATA_DIR = "JARS_DATA_DIR"

# The bundled data directory: <project root>/data. This file lives at
# <project root>/src/jars_lib/config.py, so the project root is two parents up.
PROJECT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# File names within the data directory.
CUTOFFS_FILE = "cutoffs.parquet"
NIRF_FILE = "nirf_engineering.json"
META_FILE = "meta.json"
NAME_MAP_FILE = "name_map.json"

# Default weighting between admission feasibility and NIRF quality.
DEFAULT_ALPHA = 0.5

# Fuzzy-match acceptance threshold (rapidfuzz token_sort_ratio, 0..100).
DEFAULT_NAME_MATCH_THRESHOLD = 88.0


def data_dir() -> Path:
    """Resolve the data directory: JARS_DATA_DIR if set, else the bundled data/ dir."""
    override = os.environ.get(ENV_DATA_DIR)
    return Path(override) if override else PROJECT_DATA_DIR


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
