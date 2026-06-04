"""Persistence for the offline datasets.

Cutoffs are stored as Parquet (columnar, fast to filter); NIRF scores and metadata as
JSON. Everything is loaded into memory on demand. Writes are atomic (temp file + rename)
so an interrupted update never leaves a half-written store.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .config import Paths
from .constants import CUTOFF_COLUMNS, INSTITUTE_STATE, shorten_institute_name, shorten_program_name
from .models import NirfScore

log = logging.getLogger(__name__)

_NIRF_FIELDS = ("year", "institute_name", "nirf_rank", "nirf_score")


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
        "institute_state",
    ):
        df[col] = df[col].astype("string")
    return df


def save_cutoffs(df: pd.DataFrame, paths: Paths | None = None) -> None:
    paths = paths or Paths.resolve()
    paths.ensure()
    coerced = _coerce_cutoffs(df)
    # Abbreviate names as they enter the store: IIT/NIT/IIIT prefixes in institute names
    # and long degree descriptors (B.Tech./B.S./Dual Degree) in program names.
    coerced["institute_name"] = coerced["institute_name"].map(
        lambda n: shorten_institute_name(n) if isinstance(n, str) else n
    ).astype("string")
    coerced["program_name"] = coerced["program_name"].map(
        lambda n: shorten_program_name(n) if isinstance(n, str) else n
    ).astype("string")
    # Derive institute_state from shortened name; existing values are preserved.
    missing = coerced["institute_state"].isna()
    coerced.loc[missing, "institute_state"] = coerced.loc[missing, "institute_name"].map(
        lambda n: INSTITUTE_STATE.get(n, pd.NA) if isinstance(n, str) else pd.NA
    )
    coerced["institute_state"] = coerced["institute_state"].astype("string")
    _atomic_write_bytes(paths.cutoffs, lambda p: coerced.to_parquet(p, index=False))


def load_cutoffs(paths: Paths | None = None) -> pd.DataFrame:
    paths = paths or Paths.resolve()
    if not paths.cutoffs.exists():
        return empty_cutoffs()
    try:
        return _coerce_cutoffs(pd.read_parquet(paths.cutoffs))
    except Exception as exc:
        log.error("cutoffs.parquet is unreadable (%s); treating store as empty.", exc)
        return empty_cutoffs()


# ---------------------------------------------------------------------------- nirf


def save_nirf(scores: Iterable[NirfScore], paths: Paths | None = None) -> None:
    paths = paths or Paths.resolve()
    paths.ensure()
    payload = []
    for s in scores:
        row = s.to_dict()
        # Keep NIRF names consistent with the shortened cutoff names so the fuzzy
        # institute matcher lines them up cleanly.
        row["institute_name"] = shorten_institute_name(s.institute_name)
        payload.append(row)
    _atomic_write_json(paths.nirf, payload)


def load_nirf(paths: Paths | None = None) -> list[NirfScore]:
    paths = paths or Paths.resolve()
    if not paths.nirf.exists():
        return []
    try:
        raw = json.loads(paths.nirf.read_text())
    except Exception as exc:
        log.error("nirf_engineering.json is unreadable (%s); using empty NIRF data.", exc)
        return []
    out: list[NirfScore] = []
    for i, row in enumerate(raw):
        try:
            out.append(NirfScore(**{k: row[k] for k in _NIRF_FIELDS}))
        except Exception as exc:
            log.warning("skipping malformed NIRF record %d (%s).", i, exc)
    return out


# ------------------------------------------------------------------------ name map


def save_name_map(
    lookup: dict[str, tuple[int, float]], paths: Paths | None = None
) -> None:
    """Persist the josaa_name → (nirf_rank, nirf_score) lookup so future load_data()
    calls can skip the O(N²) fuzzy-matching pass entirely."""
    paths = paths or Paths.resolve()
    paths.ensure()
    payload = {name: list(pair) for name, pair in lookup.items()}
    _atomic_write_json(paths.name_map, payload)


def load_name_map(
    paths: Paths | None = None,
) -> dict[str, tuple[int, float]] | None:
    """Load the cached name map, or return ``None`` if absent/unreadable (triggers
    on-the-fly fuzzy matching as a fallback)."""
    paths = paths or Paths.resolve()
    if not paths.name_map.exists():
        return None
    try:
        raw = json.loads(paths.name_map.read_text())
        return {name: (int(pair[0]), float(pair[1])) for name, pair in raw.items()}
    except Exception as exc:
        log.warning("name_map.json unreadable (%s); will recompute fuzzy lookup.", exc)
        return None


# ---------------------------------------------------------------------------- meta


def write_meta(meta: dict[str, Any], paths: Paths | None = None) -> None:
    paths = paths or Paths.resolve()
    paths.ensure()
    _atomic_write_json(paths.meta, meta)


def read_meta(paths: Paths | None = None) -> dict[str, Any]:
    paths = paths or Paths.resolve()
    if not paths.meta.exists():
        return {}
    try:
        return json.loads(paths.meta.read_text())
    except Exception as exc:
        log.warning("meta.json is unreadable (%s); using empty metadata.", exc)
        return {}


def update_meta(paths: Paths | None = None, **fields: Any) -> dict[str, Any]:
    """Merge ``fields`` into meta.json, stamping last_updated."""
    paths = paths or Paths.resolve()
    meta = read_meta(paths)
    meta.update(fields)
    meta["last_updated"] = datetime.now(timezone.utc).isoformat()
    write_meta(meta, paths)
    return meta
