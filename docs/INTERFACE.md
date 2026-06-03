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
    Recommendation,  # dataclass: one scored program suggestion
    Paths,           # file-path resolver
    DEFAULT_ALPHA,   # default alpha weight (0.5)
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
    alpha: float = 0.5,
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
| `home_state` | `str \| None` | When provided, home-state quota seats at NITs/IIITs/GFTIs are included |
| `institute_types` | `set[str] \| None` | Restrict to a subset of `{"IIT", "NIT", "IIIT", "GFTI"}`; `None` = all |
| `year` | `int \| None` | Cutoff year to use; defaults to the latest year in the dataset |
| `round` | `int \| None` | Counselling round to use; defaults to the latest round for the chosen year |
| `alpha` | `float` | Scoring weight in [0, 1]: `1.0` = pure feasibility, `0.0` = pure NIRF quality |
| `limit` | `int \| None` | Cap the number of results returned |

**Returns** a list of `Recommendation` objects sorted by `score` descending.

**Raises** `ValueError` if neither rank is provided, or if `alpha` is outside [0, 1].

---

## `Recommendation` fields

```python
@dataclass
class Recommendation:
    cutoff: Cutoff           # the underlying program row
    nirf_rank: int | None    # NIRF Engineering rank (1 = best), or None if not ranked
    nirf_score: float | None # NIRF score on 0–100 scale, or None
    feasibility: float       # admit likelihood in [0, 1]
    nirf_norm: float         # nirf_score / 100, in [0, 1]; 0.0 if not in NIRF
    score: float             # alpha * feasibility + (1 - alpha) * nirf_norm
```

`r.cutoff` is a `Cutoff` with fields: `year`, `round`, `institute_type`,
`institute_name`, `program_name`, `quota`, `seat_type`, `gender`, `opening_rank`,
`closing_rank`.

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
    alpha=0.5,
    data=df,                       # cutoffs DataFrame
    nirf_by_institute={...},       # {institute_name: (nirf_rank, nirf_score)}
    limit=20,
)
```

Operates directly on a pandas DataFrame. Useful if you manage the data yourself rather
than through the storage layer. The DataFrame schema must match `constants.CUTOFF_COLUMNS`.

---

## Data Directory

By default the library reads data from `data/` in the repository root. Override it with
the `JARS_DATA_DIR` environment variable:

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

# Cutoffs: provide a DataFrame with columns matching CUTOFF_COLUMNS
df = pd.DataFrame([...])
storage.save_cutoffs(df, paths)

# NIRF scores:
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
    alpha      = request.args.get("alpha",  0.5, type=float)

    results = engine.recommend(
        rank_range=rank_range,
        jee_adv_rank=adv_rank,
        jee_mains_rank=mains_rank,
        seat_type=seat_type,
        alpha=alpha,
        limit=50,
    )
    return jsonify([r.to_dict() for r in results])
```

---

## Thread Safety

`RecoEngine` is read-only after construction and is safe to share across threads.
`load_data()` and storage writes are not thread-safe if multiple threads write to the
same data directory simultaneously.
