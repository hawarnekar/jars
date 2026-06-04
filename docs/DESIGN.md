# Design: Architecture and Algorithms

## Overview

`jars` is a JEE (JoSAA) admission recommendation system structured as two layers:

1. **`jars_lib`** — a UI-agnostic Python library that scrapes, stores, and queries historical
   JoSAA cutoff data and NIRF Engineering rankings.
2. **`jars_tui`** — a Textual terminal application that embeds the library and adds an
   interactive form-and-table UI.

The design principle is strict separation: the library has no UI dependencies and exposes
plain dataclasses at its boundary. Any frontend (TUI, web app, Jupyter notebook) can embed
it without importing UI libraries.

---

## Package Layout

```
src/jars_lib/
  __init__.py          public API surface
  models.py            data structures (Cutoff, NirfScore, Recommendation)
  constants.py         canonical vocabularies, institute-name and program-name shortening functions
  config.py            data directory resolution, file paths, tuning constants
  storage.py           parquet/JSON persistence with atomic writes
  match.py             fuzzy name matching between JoSAA and NIRF institute names
  recommend.py         scoring algorithm
  engine.py            in-memory facade: load once, call recommend() many times
  update.py            orchestrates scrape + save (used by CLI and TUI)
  cli.py               argparse CLI entry point
  scrape/
    josaa.py           httpx-based JoSAA archive crawler
    josaa_playwright.py  Playwright browser-based crawler (default)
    aspform.py         ASP.NET WebForms postback helper
    nirf.py            NIRF Engineering ranking scraper
    errors.py          ScrapeError exception
  fixtures.py          bundled demo dataset (no network required)

tui/jars_tui/
  app.py               Textual App with form panel + results DataTable
```

---

## Data Model

Three dataclasses live in `models.py` and form the library's public boundary:

### `Cutoff`
One row from the JoSAA opening/closing-rank archive:

| Field | Type | Description |
|---|---|---|
| `year` | `int` | Counselling year |
| `round` | `int` | Counselling round (1–6) |
| `institute_type` | `str` | `IIT`, `NIT`, `IIIT`, or `GFTI` |
| `institute_name` | `str` | Institute name, abbreviated on save (e.g. `IIT Bombay`, `NIT Trichy`) |
| `program_name` | `str` | Program name, abbreviated on save (e.g. `CSE (4 Years, B.Tech.)`) |
| `quota` | `str` | `AI` (All India), `HS` (Home State), `OS` (Other State) |
| `seat_type` | `str` | Category: `OPEN`, `OBC-NCL`, `SC`, `ST`, `EWS` (with optional `(PwD)`) |
| `gender` | `str` | `Gender-Neutral` or `Female-only (including Supernumerary)` |
| `opening_rank` | `int \| None` | |
| `closing_rank` | `int \| None` | |

### `NirfScore`
One NIRF Engineering ranking entry:

| Field | Type | Description |
|---|---|---|
| `year` | `int` | Ranking year |
| `institute_name` | `str` | NIRF's label for the institute |
| `nirf_rank` | `int` | Rank position (1 = best) |
| `nirf_score` | `float` | Score on NIRF's 0–100 scale |

### `Recommendation`
A ranked suggestion returned by the engine, summarising one program across **all available
years** (not a single year):

| Field | Type | Description |
|---|---|---|
| `cutoff` | `Cutoff` | Most-recent year's row — used for identity/back-reference |
| `nirf_rank` | `int \| None` | Matched NIRF rank (latest dataset), if any |
| `nirf_score` | `float \| None` | Matched NIRF score, if any |
| `feasibility` | `float` | Recency-weighted admit likelihood in [0, 1] (shown as **Chance** in the UI; informational only — does not affect ordering) |
| `score` | `float` | Ranking key in [0, 1] — weighted blend of NIRF, closing, and opening goodness (see Scoring Algorithm) |
| `rank_closing` | `float \| None` | Recency-weighted closing rank across all data years (the raw value used in scoring) |
| `rank_opening` | `float \| None` | Recency-weighted opening rank across all data years with opening data |
| `in_range_years` | `list[int]` | Years the candidate's rank fell within the program's open..close band, recent→old. Empty for a "reach" |
| `window_years` | `list[int]` | Years whose closing rank fell within the candidate's ±range window. Always non-empty |
| `opening_rank_min` | `int \| None` | Smallest opening rank across the display band (in-range years if any, else window years) |
| `opening_rank_min_year` | `int \| None` | Year that opening rank occurred |
| `closing_rank_max` | `int \| None` | Largest closing rank across the display band |
| `closing_rank_max_year` | `int \| None` | Year that closing rank occurred |

Two derived properties assist display code:

| Property | Returns |
|---|---|
| `band_in_range` | `True` when Open/Close/Years reflect in-range years; `False` for a reach (window-year fallback) |
| `band_years` | The list of years Open/Close summarise: `in_range_years` if any, else `window_years` |

---

## Scoring Algorithm

### Per-year feasibility

`feasibility(rank, closing_rank)` computes the admit-likelihood from a single year's
closing rank using a logistic function on the *relative margin*:

```
relative_margin = (closing_rank - rank) / closing_rank
x               = clamp(k * relative_margin, -60, 60)
feasibility     = 1 / (1 + exp(-x))
```

`k = 6.0` is the steepness constant. With this value:

- A program whose closing rank is 20% above your rank scores ≈ 0.77 (comfortably safe).
- An exact match (closing rank = your rank) scores ≈ 0.50.
- A program whose closing rank is 20% below your rank scores ≈ 0.23 (a reach).

A missing or zero closing rank returns 0.0. The exponent is clamped to `[-60, 60]` to
prevent `math.exp` overflow on extreme inputs.

### Recency-weighted chance

Rather than using only the latest year's closing rank, the engine blends per-year
feasibility scores across **all years** using exponential recency weights:

```
weight(y) = RECENCY_DECAY ^ (ref_year - y)        # RECENCY_DECAY = 0.6
chance    = Σ weight(y) * feasibility(rank, close_y) / Σ weight(y)
```

A year that is `n` years older than `ref_year` (the most recent year in the data)
contributes `0.6^n` of the weight, so the most recent year dominates while older years
still contribute. This is what is stored in `Recommendation.feasibility` and displayed
as **Chance** (as a percentage) in both the TUI and CLI.

Each program is also reduced to one row per year before scoring: the highest-round row
for that year is used (the final, settled cutoff).

### Weighted ranking score

Each program's ranking `score` is a weighted blend of three "lower rank = better"
goodness components, each normalised to [0, 1]:

```
score = W_NIRF · g_nirf  +  W_CLOSING · g_closing  +  W_OPENING · g_opening
      =  0.6  · g_nirf   +    0.3     · g_closing   +    0.1     · g_opening
```

Because it is a *weighted sum* (not a strict priority), a large advantage on a lower-weighted
term can outweigh a small disadvantage on a higher-weighted one.

**`g_nirf` — NIRF goodness (fixed scale)**

```
g_nirf = max(0, min(1, 1 - (nirf_rank - 1) / 200))
```

Rank 1 → 1.0; rank 200+ → 0.0; institutes absent from NIRF → 0.0. The scale of 200
spans the full NIRF Engineering list, so the curve is independent of which institutes
happen to appear in a given result set. Only the **latest NIRF dataset** is used.

**`g_closing` / `g_opening` — rank goodness (min-max, per exam family)**

The recency-weighted closing and opening ranks are min-max normalised *within each exam
family* (IIT vs NIT/IIIT/GFTI), so the best-in-family program scores 1.0:

```
g_closing = (max_closing - rank_closing) / (max_closing - min_closing)
```

Normalising per-family keeps IIT and non-IIT programs comparable through the NIRF term
(which uses a global scale) while avoiding artefacts from the two exam scales having
different numerical ranges.

A missing opening rank falls back to the program's closing goodness so the tertiary term
never penalises programs with incomplete data.

Results are sorted by `score` descending.

---

## JEE Rank Partitioning

JoSAA runs two parallel rank scales:

- **JEE Advanced rank** — used exclusively for IIT seats (~1.8 lakh candidates).
- **JEE Mains CRL rank** — used for NIT, IIIT, and GFTI seats (~11 lakh candidates).

`RecoEngine.recommend()` accepts both ranks and merges the results:

- Only `jee_adv_rank` → query `IIT_TYPES` only.
- Only `jee_mains_rank` → query `NON_IIT_TYPES` only.
- Both → query each family with its own rank scale, then merge and re-sort by `score`.
  The merge is safe because `g_closing`/`g_opening` are normalised within each family, so
  only the globally-comparable `g_nirf` term influences cross-family ordering.

The split is defined in `constants.py`:

```python
IIT_TYPES     = frozenset({"IIT"})
NON_IIT_TYPES = frozenset({"NIT", "IIIT", "GFTI"})
```

---

## NIRF Name Matching

JoSAA and NIRF use slightly different institute name spellings. `match.py` resolves them
with fuzzy matching:

1. Abbreviate both name sets via `shorten_institute_name()` (e.g. `Indian Institute of
   Technology Bombay → IIT Bombay`) so long and short forms compare equal.
2. Normalise: lowercase, collapse whitespace, strip hyphens/commas.
3. For each JoSAA name, call `rapidfuzz.process.extractOne` with `fuzz.token_sort_ratio`
   against the normalised NIRF names.
4. Accept matches scoring ≥ 88 (default threshold in `config.DEFAULT_NAME_MATCH_THRESHOLD`).
5. Build a lookup `josaa_name → (nirf_rank, nirf_score)` used at scoring time.

The lookup is built once in `RecoEngine.__post_init__` and reused for all queries.

---

## Storage

`storage.py` manages three files in the data directory:

| File | Format | Contents |
|---|---|---|
| `cutoffs.parquet` | Apache Parquet | All JoSAA opening/closing rank rows |
| `nirf_engineering.json` | JSON array | NIRF Engineering ranking entries |
| `meta.json` | JSON object | Last-updated timestamp, row counts, years fetched |

**Schema enforcement** — `_coerce_cutoffs()` enforces column presence and dtype on every
load and save: `year`, `round`, `opening_rank`, `closing_rank` are nullable `Int64`;
string columns use pandas `StringDtype`. This prevents silent type drift between scrape
runs.

**Name normalisation** — `save_cutoffs` abbreviates institute names (`Indian Institute of
Technology → IIT`, `National Institute of Technology → NIT`, `Indian Institute of
Information Technology → IIIT`) and program names (`Bachelor of Technology → B.Tech.`,
`Bachelor of Science → B.S.`, dual-degree/integrated phrases → `B.Tech. + M.Tech.` or
`B.S. + M.S.`, etc.) as data enters the store. Both `save_nirf` and `match._normalise`
apply the same institute abbreviation so names stay consistent across all three files.
The shortening functions (`shorten_institute_name`, `shorten_program_name`) live in
`constants.py` and are idempotent.

**Atomic writes** — every save writes to a temp file in the same directory, then calls
`os.replace()` to atomically rename it over the target. An interrupted update never
leaves a partially-written file.

**Data directory resolution** — `config.data_dir()` resolves with a three-level
precedence: `$JARS_DATA_DIR` (explicit override) → the source-tree `data/` directory (only
when it exists, i.e. an editable checkout) → `platformdirs.user_data_dir("jars")` (a
writable per-user directory for installed wheels). This lets embedding apps and installed
packages find a sensible writable location without any code changes.

---

## JoSAA Scraping

The JoSAA opening/closing rank archive is an ASP.NET WebForms page with cascading
dropdowns (Year → Round → Institute Type → Institute → Program → Seat Type). The server
rejects plain HTTP postbacks (it 302-redirects them to `ErrMsg.aspx`), so the default
backend drives the page with a real browser.

### Playwright backend (default)

`scrape/josaa_playwright.py` — `PlaywrightJosaaScraper`:

1. Opens Chromium in headless mode and navigates to the archive URL.
2. Discovers all `<select>` elements in-page via `page.eval_on_selector_all`.
3. For each Year × Round × Institute Type combination: sets the native select value
   and dispatches a `change` event, which triggers the ASP.NET `__doPostBack` autopostback.
   The jQuery "Chosen" plugin's custom widget is bypassed entirely by setting the underlying
   native `<select>` directly.
4. On the leaf (Institute / Branch / Seat Type), selects the "All" option where available,
   submits the form, and waits for navigation.
5. Calls `josaa.parse_result_table()` on the rendered page HTML.

### httpx backend (legacy)

`scrape/josaa.py` — `JosaaClient` + `AspForm`:

Implements the same crawl strategy using `httpx` and `aspform.py`, which reconstructs the
ASP.NET `__VIEWSTATE` / `__EVENTVALIDATION` payload for each postback. Currently
server-blocked (the live endpoint rejects it); kept for unit testing with
`pytest-httpx` mocks.

### Result table parsing

`josaa.parse_result_table()` is shared by both backends:

1. Finds the widest HTML table containing both "institute" and "closing" in its header text.
2. Maps header cell text to canonical column names using case-insensitive substring
   matching (robust to minor markup changes).
3. Strips stray whitespace and converts rank text like `"1234P"` (preparatory seats)
   to integers.

### NIRF scraping

`scrape/nirf.py` — `scrape_nirf(year)`:

Fetches the NIRF Engineering ranking HTML page and parses it with BeautifulSoup. Each
data row is identified by its first cell matching the NIRF institute-ID pattern
(`IR-[A-Z]...`), which reliably distinguishes real data rows from the interleaved
"More Details" sub-rows that follow each institute.

---

## Update Orchestration

`update.py` — `update_database()`:

1. Dispatches to the chosen scrape backend and accumulates cutoff rows.
   - **`--resume`** mode loads the existing store first and skips `(year, round, type)`
     combinations already present. The scraper checkpoints after each `(year, round)` pair
     so partial progress survives a crash.
   - **`--force`** bypasses the empty-overwrite guard that otherwise refuses to clobber a
     non-empty store with zero scraped rows (safety against a silent scrape failure).
2. Saves the cutoff DataFrame atomically.
3. Derives the NIRF year from the scraped cutoff years (or the `--nirf-year` flag) and
   scrapes NIRF. NIRF failure is non-fatal — existing NIRF data is kept.
4. Writes `meta.json` with updated stats, a UTC timestamp, and per-`(year, round)` row
   counts (`round_counts`) so a thin partial slice is visible via `jars-lib info`.

Both the CLI and the TUI call this function, passing an optional `progress` callback for
status updates.

---

## TUI Architecture

`tui/jars_tui/app.py` — `RecoApp(App)`:

- **Left panel** (`#form`): a `VerticalScroll` containing labelled `Input` and `Select`
  widgets for rank, range, category, gender, home state, and institute types.
- **Right panel** (`#results`): a `DataTable` with two flexible-width columns (Institute,
  Program) that reflow on terminal resize, plus fixed-width columns: `Category`, `Quota`,
  `Open` (smallest opening rank across the display band, with its year), `Close` (largest
  closing rank across the display band, with its year), `Years` (band years recent→old;
  prefixed `~` when the band comes from the window-year reach fallback rather than in-range
  years), `NIRF` (rank), `Chance` (recency-weighted admit likelihood as %). The CLI renders
  the same columns in a plain-text auto-sized table.

  The **display band** is the in-range years if the candidate's rank fell inside the
  opening..closing band in any year; otherwise the window years (years whose closing rank
  landed within the ±range). This ensures reaches show the relevant ranks rather than
  blank fields, helping users understand why the chance is low.

Text wrapping in cells uses `textwrap.wrap()` capped at 6 lines; the `DataTable` row
height is set to the maximum wrapped line count of the two flexible columns.

The live scrape (`action_update`) runs in a `@work(thread=True)` worker to avoid
blocking the event loop. Progress messages are pushed back to the UI thread with
`call_from_thread`.

On startup, if data exists, `action_recommend()` fires automatically so the table is
populated immediately.
