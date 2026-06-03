"""Persistence for the offline datasets.

Cutoffs are stored as Parquet (columnar, fast to filter); NIRF scores and metadata as
JSON. Everything is loaded into memory on demand. Writes are atomic (temp file + rename)
so an interrupted update never leaves a half-written store.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .config import Paths
from .constants import CUTOFF_COLUMNS
from .models import NirfScore


# --------------------------------------------------------------------------- helpers


def _atomic_write_bytes(path: Path, write_fn) -> None:
    """Write via a temp file in the same dir, then rename over the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        write_fn(tmp_path)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _atomic_write_json(path: Path, obj: Any) -> None:
    _atomic_write_bytes(
        path, lambda p: p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    )


# ------------------------------------------------------------------------- cutoffs


def empty_cutoffs() -> pd.DataFrame:
    """An empty, correctly-typed cutoffs frame."""
    df = pd.DataFrame(columns=list(CUTOFF_COLUMNS))
    return _coerce_cutoffs(df)


def _coerce_cutoffs(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure expected columns and dtypes; ranks are nullable integers."""
    for col in CUTOFF_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[list(CUTOFF_COLUMNS)].copy()
    for col in ("year", "round", "opening_rank", "closing_rank"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in (
        "institute_type",
        "institute_name",
        "program_name",
        "quota",
        "seat_type",
        "gender",
    ):
        df[col] = df[col].astype("string")
    return df


def save_cutoffs(df: pd.DataFrame, paths: Paths | None = None) -> None:
    paths = paths or Paths.resolve()
    paths.ensure()
    coerced = _coerce_cutoffs(df)
    _atomic_write_bytes(paths.cutoffs, lambda p: coerced.to_parquet(p, index=False))


def load_cutoffs(paths: Paths | None = None) -> pd.DataFrame:
    paths = paths or Paths.resolve()
    if not paths.cutoffs.exists():
        return empty_cutoffs()
    return _coerce_cutoffs(pd.read_parquet(paths.cutoffs))


# ---------------------------------------------------------------------------- nirf


def save_nirf(scores: Iterable[NirfScore], paths: Paths | None = None) -> None:
    paths = paths or Paths.resolve()
    paths.ensure()
    payload = [s.to_dict() for s in scores]
    _atomic_write_json(paths.nirf, payload)


def load_nirf(paths: Paths | None = None) -> list[NirfScore]:
    paths = paths or Paths.resolve()
    if not paths.nirf.exists():
        return []
    raw = json.loads(paths.nirf.read_text())
    return [NirfScore(**row) for row in raw]


# ---------------------------------------------------------------------------- meta


def write_meta(meta: dict[str, Any], paths: Paths | None = None) -> None:
    paths = paths or Paths.resolve()
    paths.ensure()
    _atomic_write_json(paths.meta, meta)


def read_meta(paths: Paths | None = None) -> dict[str, Any]:
    paths = paths or Paths.resolve()
    if not paths.meta.exists():
        return {}
    return json.loads(paths.meta.read_text())


def update_meta(paths: Paths | None = None, **fields: Any) -> dict[str, Any]:
    """Merge ``fields`` into meta.json, stamping last_updated."""
    paths = paths or Paths.resolve()
    meta = read_meta(paths)
    meta.update(fields)
    meta["last_updated"] = datetime.now(timezone.utc).isoformat()
    write_meta(meta, paths)
    return meta
