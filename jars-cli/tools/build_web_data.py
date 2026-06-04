"""Export the offline jars dataset into a compact, browser-friendly bundle for jars-web.

The web app cannot run Python, so it ships a pre-built dataset that the TypeScript port
of the engine consumes directly. To guarantee the web data matches what the Python engine
sees, this script reuses jars_lib's *own* reductions rather than reimplementing them:

* ``jars_lib.recommend._yearly_reps`` collapses the 500k+ raw rows to one representative
  row per (program-key, year) — exactly the set the engine iterates over. This is the bulk
  of the size win (≈523k → ≈88k rows).
* The engine's NIRF name-match lookup (``RecoEngine._nirf_lookup``, seeded from the cached
  ``name_map.json``) is pre-joined per institute, so the browser never needs the fuzzy
  matcher.

Outputs (paths relative to the repo root, overridable via --out-data / --out-golden):

* ``jars-web/public/data/cutoffs.v1.json`` — columnar, dictionary-encoded dataset.
* ``jars-web/tests/golden/golden.json``    — query specs + their engine.recommend() output,
  used by the TS parity tests to prove the port matches Python.

Run from anywhere::

    python jars-cli/tools/build_web_data.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from jars_lib import load_data
from jars_lib.constants import GENDER_FEMALE, GENDER_NEUTRAL
from jars_lib.recommend import _KEY_COLS, _yearly_reps  # reuse the engine's own reduction

# Bump when the on-disk schema changes; the filename carries the major version so the
# browser can cache aggressively and bust on a new build.
SCHEMA_VERSION = 1
DATA_FILENAME = f"cutoffs.v{SCHEMA_VERSION}.json"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DATA = REPO_ROOT / "jars-web" / "public" / "data" / DATA_FILENAME
DEFAULT_OUT_GOLDEN = REPO_ROOT / "jars-web" / "tests" / "golden" / "golden.json"


def _opt_int(value: Any) -> int | None:
    """Coerce a possibly-NaN numeric cell to ``int`` or ``None``."""
    if value is None or pd.isna(value):
        return None
    return int(value)


class _Interner:
    """Assigns a stable, insertion-ordered integer id to each distinct string."""

    def __init__(self) -> None:
        self._ids: dict[str, int] = {}
        self.values: list[str] = []

    def id(self, value: str) -> int:
        idx = self._ids.get(value)
        if idx is None:
            idx = len(self.values)
            self._ids[value] = idx
            self.values.append(value)
        return idx


def build_dataset(engine) -> dict[str, Any]:
    """Build the columnar, dictionary-encoded dataset from a loaded engine."""
    reps = _yearly_reps(engine.cutoffs)
    if reps.empty:
        raise SystemExit("No cutoff rows after reduction — is the dataset seeded?")

    # institute_type and institute_state are functionally determined by institute_name,
    # and NIRF is per-institute, so normalise them out of the per-row arrays into a single
    # per-institute table keyed by the interned institute id.
    nirf_lookup = engine._nirf_lookup or {}

    institutes = _Interner()
    programs = _Interner()
    quotas = _Interner()
    seats = _Interner()
    genders = _Interner()
    states = _Interner()
    inst_types = _Interner()

    # Per-institute metadata, filled lazily as institutes are first seen.
    inst_meta: dict[int, dict[str, Any]] = {}

    col_inst: list[int] = []
    col_prog: list[int] = []
    col_quota: list[int] = []
    col_seat: list[int] = []
    col_gender: list[int] = []
    col_year: list[int] = []
    col_open: list[int | None] = []
    col_close: list[int] = []

    # Iterate in a deterministic order so output is byte-stable across runs (clean diffs).
    reps = reps.sort_values(_KEY_COLS + ["year"]).reset_index(drop=True)

    for row in reps.itertuples(index=False):
        name = str(row.institute_name)
        iid = institutes.id(name)
        if iid not in inst_meta:
            state = row.institute_state
            state = str(state) if isinstance(state, str) and state else None
            nirf = nirf_lookup.get(name)
            inst_meta[iid] = {
                "type": inst_types.id(str(row.institute_type)),
                "state": states.id(state) if state is not None else -1,
                "nirf_rank": int(nirf[0]) if nirf else None,
                "nirf_score": round(float(nirf[1]), 2) if nirf else None,
            }

        col_inst.append(iid)
        col_prog.append(programs.id(str(row.program_name)))
        col_quota.append(quotas.id(str(row.quota)))
        col_seat.append(seats.id(str(row.seat_type)))
        col_gender.append(genders.id(str(row.gender)))
        col_year.append(int(row.year))
        col_open.append(_opt_int(row.opening_rank))
        col_close.append(int(row.closing_rank))

    institute_table = [inst_meta[i] for i in range(len(institutes.values))]

    meta = dict(engine.meta or {})
    meta.update(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        row_count=len(col_close),
        institute_count=len(institutes.values),
        program_count=len(programs.values),
    )

    return {
        "meta": meta,
        "dict": {
            "institutes": institutes.values,
            "programs": programs.values,
            "institute_types": inst_types.values,
            "quotas": quotas.values,
            "seat_types": seats.values,
            "genders": genders.values,
            "states": states.values,
            # Mirror the canonical gender labels so the TS engine's gender-pool logic can
            # reference them by meaning rather than guessing from index.
            "gender_neutral": GENDER_NEUTRAL,
            "gender_female": GENDER_FEMALE,
        },
        "institutes": institute_table,
        "rows": {
            "inst": col_inst,
            "prog": col_prog,
            "quota": col_quota,
            "seat": col_seat,
            "gender": col_gender,
            "year": col_year,
            "open": col_open,
            "close": col_close,
        },
    }


# Query specs exercised by the parity tests. Chosen to cover every branch of the engine:
# mains-only / adv-only / both, each category, female pool, home-state HS/OS split,
# institute-type filters, varying ranges, and a pinned year/round.
_GOLDEN_SPECS: list[dict[str, Any]] = [
    {"rank_range": 2000, "jee_mains_rank": 25000},
    {"rank_range": 5000, "jee_mains_rank": 25000, "seat_type": "OBC-NCL"},
    {"rank_range": 1000, "jee_adv_rank": 3000},
    {"rank_range": 2000, "jee_adv_rank": 3000, "jee_mains_rank": 25000},
    {"rank_range": 2000, "jee_mains_rank": 25000, "seat_type": "SC"},
    {"rank_range": 2000, "jee_mains_rank": 25000, "seat_type": "ST"},
    {"rank_range": 2000, "jee_mains_rank": 25000, "seat_type": "EWS"},
    {"rank_range": 3000, "jee_mains_rank": 50000, "seat_type": "OPEN", "gender": GENDER_FEMALE},
    {"rank_range": 2000, "jee_mains_rank": 25000, "home_state": "Rajasthan"},
    {"rank_range": 2000, "jee_mains_rank": 25000, "home_state": "Tamil Nadu"},
    {"rank_range": 2000, "jee_mains_rank": 25000, "institute_types": ["NIT"]},
    {"rank_range": 2000, "jee_mains_rank": 25000, "institute_types": ["IIIT", "GFTI"]},
    {"rank_range": 1500, "jee_adv_rank": 8000, "institute_types": ["IIT"]},
    {"rank_range": 2000, "jee_mains_rank": 25000, "year": 2024},
    {"rank_range": 2000, "jee_mains_rank": 25000, "year": 2023, "round": 6},
    {"rank_range": 500, "jee_mains_rank": 100000, "seat_type": "OBC-NCL", "limit": 25},
    {"rank_range": 10000, "jee_mains_rank": 5000, "seat_type": "OPEN"},
    {"rank_range": 2000, "jee_adv_rank": 500},
    {"rank_range": 4000, "jee_mains_rank": 250000, "seat_type": "OPEN"},
    {
        "rank_range": 3000,
        "jee_adv_rank": 6000,
        "jee_mains_rank": 40000,
        "seat_type": "OBC-NCL",
        "home_state": "Maharashtra",
        "gender": GENDER_FEMALE,
    },
]


def build_golden(engine) -> dict[str, Any]:
    """Run each golden spec through the engine and capture its serialised output."""
    cases = []
    for spec in _GOLDEN_SPECS:
        kwargs = dict(spec)
        rank_range = kwargs.pop("rank_range")
        if "institute_types" in kwargs and kwargs["institute_types"] is not None:
            kwargs["institute_types"] = set(kwargs["institute_types"])
        results = engine.recommend(rank_range, **kwargs)
        # Re-serialise the spec with JSON-friendly types (sets -> sorted lists).
        out_spec = dict(spec)
        if isinstance(out_spec.get("institute_types"), list):
            out_spec["institute_types"] = sorted(out_spec["institute_types"])
        cases.append({"spec": out_spec, "results": [r.to_dict() for r in results]})
    return {"schema_version": SCHEMA_VERSION, "cases": cases}


def _write_json(path: Path, payload: dict[str, Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-data", type=Path, default=DEFAULT_OUT_DATA)
    ap.add_argument("--out-golden", type=Path, default=DEFAULT_OUT_GOLDEN)
    ap.add_argument("--skip-golden", action="store_true", help="Only build the dataset.")
    args = ap.parse_args()

    engine = load_data()
    if engine.is_empty:
        raise SystemExit("Engine has no data. Run `jars-lib seed-demo` or `jars-lib update` first.")

    dataset = build_dataset(engine)
    n = _write_json(args.out_data, dataset)
    print(
        f"dataset  → {args.out_data}  "
        f"({dataset['meta']['row_count']} rows, {dataset['meta']['institute_count']} institutes, "
        f"{n / 1e6:.2f} MB raw)"
    )

    if not args.skip_golden:
        golden = build_golden(engine)
        gn = _write_json(args.out_golden, golden)
        total = sum(len(c["results"]) for c in golden["cases"])
        print(f"golden   → {args.out_golden}  ({len(golden['cases'])} cases, {total} rows, {gn / 1e6:.2f} MB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
