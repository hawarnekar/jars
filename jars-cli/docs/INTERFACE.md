# Interface Guide: Embedding jars_lib

This document explains how to use `jars_lib` as a library from your own application —
a web app, Jupyter notebook, REST API, or any other Python program.

---

## Installation

```bash
pip install -e /path/to/jars         # minimal (no TUI, no scraper)
pip install -e /path/to/jars[tui]    # + Textual TUI
pip install -e /path/to/jars[scrape] # + Playwright scraper
pip install -e /path/to/jars[all]    # everything
```

---

## Public API

The public API is exported from `jars_lib.__init__`:

```python
from jars_lib import (
    load_data,       # load offline data into an engine instance
    RecoEngine,      # in-memory engine class
    recommend,       # low-level recommend function (operates on a DataFrame)
    feasibility,     # admit-likelihood score for a single rank/closing-rank pair
    Cutoff,          # dataclass: one JoSAA opening/closing rank row
    NirfScore,       # dataclass: one NIRF Engineering ranking entry
    Recommendation,  # dataclass: one ranked program suggestion
    Paths,           # file-path resolver
    INSTITUTE_TYPES, # ("IIT", "NIT", "IIIT", "GFTI")
    IIT_TYPES,       # frozenset: {"IIT"}
    NON_IIT_TYPES,   # frozenset: {"NIT", "IIIT", "GFTI"}
    SEAT_TYPES,      # tuple of valid seat type strings
    GENDERS,         # tuple: (GENDER_NEUTRAL, GENDER_FEMALE)
    GENDER_NEUTRAL,  # "Gender-Neutral"
    GENDER_FEMALE,   # "Female-only (including Supernumerary)"
)
```

---

## Typical Usage

### 1. Load the offline data once

```python
from jars_lib import load_data

engine = load_data()
```

`load_data()` reads `cutoffs.parquet`, `nirf_engineering.json`, and `meta.json` from
the data directory (see [Data Directory](#data-directory)), builds the NIRF name-match
lookup, and returns a `RecoEngine`. Call it once at startup and reuse the instance.

### 2. Get recommendations

```python
results = engine.recommend(
    rank_range=2000,
    jee_mains_rank=25000,
    seat_type="OBC-NCL",
)

for r in results:
    print(
        r.cutoff.institute_name,
        r.cutoff.program_name,
        r.cutoff.closing_rank,
        f"score={r.score:.3f}",
    )
```

---

## `RecoEngine.recommend()`

```python
engine.recommend(
    rank_range: int,
    *,
    jee_adv_rank: int | None = None,
    jee_mains_rank: int | None = None,
    seat_type: str = "OPEN",
    gender: str = GENDER_NEUTRAL,
    home_state: str | None = None,
    institute_types: set[str] | None = None,
    year: int | None = None,
    round: int | None = None,
    limit: int | None = None,
) -> list[Recommendation]
```

**At least one of `jee_adv_rank` or `jee_mains_rank` must be provided.**

| Parameter | Type | Description |
|---|---|---|
| `rank_range` | `int` | ± window: programs with `closing_rank` in `[rank - rank_range, rank + rank_range]` are included |
| `jee_adv_rank` | `int \| None` | JEE Advanced rank (selects IIT seats) |
| `jee_mains_rank` | `int \| None` | JEE Mains CRL rank (selects NIT/IIIT/GFTI seats) |
| `seat_type` | `str` | Category, e.g. `"OPEN"`, `"OBC-NCL"`, `"SC"`, `"ST"`, `"EWS"`, or their `"(PwD)"` variants |
| `gender` | `str` | `GENDER_NEUTRAL` or `GENDER_FEMALE` (female candidates may use either) |
| `home_state` | `str \| None` | When provided, HS quota is returned for institutes located in that state and OS quota for all others. When `None`, both HS and OS rows are included. |
| `institute_types` | `set[str] \| None` | Restrict to a subset of `{"IIT", "NIT", "IIIT", "GFTI"}`; `None` = all |
| `year` | `int \| None` | Pin to a specific cutoff year; `None` (default) considers all years |
| `round` | `int \| None` | Pin to a specific counselling round; `None` (default) uses each year's highest round |
| `limit` | `int \| None` | Cap the number of results returned |

**Returns** a list of `Recommendation` objects sorted by `score` descending (see the
Scoring Algorithm in `docs/DESIGN.md`).

**Raises** `ValueError` if neither rank is provided.

---

## `Recommendation` fields

```python
@dataclass
class Recommendation:
    cutoff: Cutoff                    # most-recent year's row (identity/back-reference)
    nirf_rank: int | None             # NIRF Engineering rank (1 = best), latest dataset
    nirf_score: float | None          # NIRF score on 0–100 scale, or None
    feasibility: float                # recency-weighted admit likelihood in [0, 1] ("Chance")
    score: float                      # ranking key in [0, 1] (weighted blend — see DESIGN.md)
    rank_closing: float | None        # recency-weighted closing rank (used in scoring)
    rank_opening: float | None        # recency-weighted opening rank (used in scoring)
    in_range_years: list[int]         # years candidate's rank was within open..close, recent→old
    window_years: list[int]           # years the closing rank was in the candidate's ±range window
    opening_rank_min: int | None      # smallest opening rank across the display band
    opening_rank_min_year: int | None # year of opening_rank_min
    closing_rank_max: int | None      # largest closing rank across the display band
    closing_rank_max_year: int | None # year of closing_rank_max

    # derived properties (not constructor arguments):
    # band_in_range: bool     — True when Open/Close reflect in-range years; False for reach fallback
    # band_years: list[int]   — in_range_years if any, else window_years
```

A recommendation summarises one program across **all available years**. `cutoff` holds
the most-recent year's row for identity. The **display band** (`opening_rank_min`,
`closing_rank_max`, `band_years`) shows in-range years when the rank cleared the cutoff,
or the window years (reach years) otherwise — so reaches are never displayed as blank.

`r.cutoff` has fields: `year`, `round`, `institute_type`, `institute_name`,
`program_name`, `quota`, `seat_type`, `gender`, `opening_rank`, `closing_rank`,
`institute_state` (the Indian state where the institute is located, or `None` if unknown).

Both `Cutoff` and `Recommendation` expose a `.to_dict()` method that returns a plain
`dict[str, Any]` suitable for JSON serialisation or DataFrame construction.

---

## Serialisation

```python
import json

results = engine.recommend(rank_range=2000, jee_mains_rank=25000)

# To a list of dicts (JSON-serialisable):
payload = [r.to_dict() for r in results]
print(json.dumps(payload[:3], indent=2))

# To a pandas DataFrame:
import pandas as pd
df = pd.DataFrame([r.to_dict() for r in results])
```

---

## Inspecting Available Data

```python
engine.is_empty           # True if no cutoffs are loaded
engine.years()            # [2022, 2023, 2024, ...]
engine.rounds(year=2024)  # [1, 2, 3, 4, 5, 6]
len(engine.cutoffs)       # total cutoff rows
len(engine.nirf)          # number of NIRF institutes
engine.meta               # {"last_updated": "...", "cutoff_rows": ..., ...}
```

---

## Low-Level Functions

These are available for advanced use but most callers should use `RecoEngine` instead.

### `feasibility(rank, closing_rank)`

```python
from jars_lib import feasibility

score = feasibility(rank=5000, closing_rank=5500)   # → ~0.70
score = feasibility(rank=5000, closing_rank=4500)   # → ~0.30
score = feasibility(rank=5000, closing_rank=None)   # → 0.0
```

Returns a float in [0, 1] representing the admit likelihood implied by a single
closing rank.

### `recommend()` (module-level)

```python
from jars_lib import recommend
import pandas as pd

results = recommend(
    rank=5000,
    rank_range=2000,
    seat_type="OPEN",
    data=df,                       # cutoffs DataFrame
    nirf_by_institute={...},       # {institute_name: (nirf_rank, nirf_score)}
    limit=20,
)
```

Operates directly on a pandas DataFrame. Useful if you manage the data yourself rather
than through the storage layer. The DataFrame schema must match `constants.CUTOFF_COLUMNS`.

---

## Data Directory

The data directory is resolved with three-level precedence:
1. `$JARS_DATA_DIR` environment variable (explicit override).
2. The source-tree `data/` directory — used when running from an editable checkout.
3. `platformdirs.user_data_dir("jars")` — a writable per-user location for installed wheels.

Override via the environment variable:

```bash
JARS_DATA_DIR=/path/to/my/data python my_app.py
```

Or pass a `Paths` object at load time:

```python
from jars_lib import load_data, Paths
from pathlib import Path

engine = load_data(Paths(root=Path("/path/to/my/data")))
```

---

## Populating the Dataset Programmatically

### Seed the bundled demo data (no network)

```python
from jars_lib.update import seed_demo

meta = seed_demo()
print(meta)  # {"source": "demo", "cutoff_rows": ..., ...}
engine = load_data()
```

### Run a full or partial live update

```python
from jars_lib.update import update_database

meta = update_database(
    years=["2024"],
    rounds=["6"],
    institute_types=["NIT", "IIIT"],
    progress=print,        # optional: called with status strings
)
engine = load_data()       # reload after update
```

### Write your own data

```python
from jars_lib import storage, Paths, NirfScore
from pathlib import Path
import pandas as pd

paths = Paths(root=Path("/my/data"))

# Cutoffs: provide a DataFrame with columns matching CUTOFF_COLUMNS.
# save_cutoffs automatically abbreviates institute names (IIT/NIT/IIIT prefixes) and
# program names (Bachelor of Technology → B.Tech., etc.) as data enters the store.
df = pd.DataFrame([...])
storage.save_cutoffs(df, paths)

# NIRF scores: institute names are also abbreviated on save to stay consistent with
# the cutoffs store.
scores = [NirfScore(year=2024, institute_name="...", nirf_rank=1, nirf_score=85.2)]
storage.save_nirf(scores, paths)

engine = load_data(paths)
```

---

## Constants Reference

```python
from jars_lib import INSTITUTE_TYPES, SEAT_TYPES, GENDERS, GENDER_NEUTRAL, GENDER_FEMALE

INSTITUTE_TYPES  # ("IIT", "NIT", "IIIT", "GFTI")
SEAT_TYPES       # ("OPEN", "OPEN (PwD)", "EWS", "EWS (PwD)", "OBC-NCL", "OBC-NCL (PwD)",
                 #  "SC", "SC (PwD)", "ST", "ST (PwD)")
GENDERS          # ("Gender-Neutral", "Female-only (including Supernumerary)")
GENDER_NEUTRAL   # "Gender-Neutral"
GENDER_FEMALE    # "Female-only (including Supernumerary)"
```

These constants match the labels used in the JoSAA dataset. Pass them directly to
`recommend()` rather than hard-coding string literals.

---

## Minimal Example: Flask JSON API

```python
from flask import Flask, request, jsonify
from jars_lib import load_data

app = Flask(__name__)
engine = load_data()  # load once at startup

@app.get("/recommend")
def recommend():
    mains_rank = request.args.get("mains_rank", type=int)
    adv_rank   = request.args.get("adv_rank",   type=int)
    rank_range = request.args.get("range",  2000, type=int)
    seat_type  = request.args.get("category", "OPEN")

    results = engine.recommend(
        rank_range=rank_range,
        jee_adv_rank=adv_rank,
        jee_mains_rank=mains_rank,
        seat_type=seat_type,
        limit=50,
    )
    return jsonify([r.to_dict() for r in results])
```

---

## Thread Safety

`RecoEngine` is read-only after construction and is safe to share across threads.
`load_data()` and storage writes are not thread-safe if multiple threads write to the
same data directory simultaneously.

---

## The Web Port (`jars-web`)

GitHub Pages is static, so `jars_lib` cannot run server-side for the web UI. Instead the
sibling [`jars-web`](../../jars-web) app:

1. **Pre-builds a compact dataset offline.** `tools/build_web_data.py` loads the engine and
   reuses its *own* reductions — `jars_lib.recommend._yearly_reps` to collapse the cutoffs to
   one row per (program, year), and `RecoEngine._nirf_lookup` to pre-join NIRF — then emits a
   columnar, dictionary-encoded JSON (~88k rows, ~0.5 MB gzipped). Because the export reuses
   the library's functions, the web data is exactly what the Python engine sees.

   ```bash
   python jars-cli/tools/build_web_data.py        # writes jars-web/public/data + goldens
   ```

   Two subtleties the exporter handles for correctness: `institute_type` is **per row** (it is
   part of the engine key and a few institutes were reclassified across years, e.g. IIEST
   Shibpur GFTI→NIT), and `institute_state` is resolved the same way `recommend._filter` does
   (stored value, else the `INSTITUTE_STATE` name-map fallback). It does **not** support the
   `round` argument — pinning a round can't be reproduced from round-collapsed data — which is
   fine because the web UI (like the TUI) has no round selector.

2. **Runs a TypeScript port of the engine** (`jars-web/src/engine/`) that mirrors
   `recommend.py` / `engine.py` function-for-function.

3. **Guarantees parity** via golden tests: `build_web_data.py` also emits query specs with
   their `engine.recommend(...).to_dict()` output, and `jars-web/tests/engine.parity.test.ts`
   asserts the TS engine reproduces them. **If you change the scoring algorithm here,
   regenerate the dataset/goldens and run the web tests** — they will fail on any divergence.
