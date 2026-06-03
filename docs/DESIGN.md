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
  constants.py         canonical vocabularies (seat types, quotas, institute families)
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
| `institute_name` | `str` | Full institute name (JoSAA's label) |
| `program_name` | `str` | Academic program / branch |
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
A scored suggestion returned by the engine, wrapping a `Cutoff` with scoring signals:

| Field | Type | Description |
|---|---|---|
| `cutoff` | `Cutoff` | The underlying program row |
| `nirf_rank` | `int \| None` | Matched NIRF rank, if any |
| `nirf_score` | `float \| None` | Matched NIRF score, if any |
| `feasibility` | `float` | Admit likelihood in [0, 1] |
| `nirf_norm` | `float` | Normalised NIRF score in [0, 1] |
| `score` | `float` | Final blended score in [0, 1] |

---

## Scoring Algorithm

### Feasibility signal

`feasibility(rank, closing_rank)` uses a logistic function on the *relative margin*
between the candidate's rank and the program's historical closing rank:

```
relative_margin = (closing_rank - rank) / closing_rank
feasibility     = 1 / (1 + exp(-k * relative_margin))
```

`k = 6.0` is the steepness constant. With this value:

- A program whose closing rank is 20% above your rank scores ≈ 0.77 (comfortably safe).
- An exact match (closing rank = your rank) scores ≈ 0.50.
- A program whose closing rank is 20% below your rank scores ≈ 0.23 (a reach).

A missing or zero closing rank returns 0.0.

### NIRF signal

The NIRF score (0–100) is divided by 100 to normalise it to [0, 1]:

```
nirf_norm = nirf_score / 100
```

Institutes absent from NIRF receive `nirf_norm = 0.0` and are still ranked, using
feasibility alone.

### Blended score

```
score = alpha * feasibility + (1 - alpha) * nirf_norm
```

`alpha` is user-controlled in [0, 1]:

- `alpha = 1.0` — rank purely by safety; NIRF is ignored.
- `alpha = 0.0` — rank purely by NIRF quality; admission likelihood is ignored.
- `alpha = 0.5` (default) — equal weight on both signals.

Results are sorted by `score` descending.

---

## JEE Rank Partitioning

JoSAA runs two parallel rank scales:

- **JEE Advanced rank** — used exclusively for IIT seats (~1.8 lakh candidates).
- **JEE Mains CRL rank** — used for NIT, IIIT, and GFTI seats (~11 lakh candidates).

`RecoEngine.recommend()` accepts both ranks and merges the results:

- Only `jee_adv_rank` → query `IIT_TYPES` only.
- Only `jee_mains_rank` → query `NON_IIT_TYPES` only.
- Both → query each family with its own rank scale, then merge and re-sort by score.

The split is defined in `constants.py`:

```python
IIT_TYPES     = frozenset({"IIT"})
NON_IIT_TYPES = frozenset({"NIT", "IIIT", "GFTI"})
```

---

## NIRF Name Matching

JoSAA and NIRF use slightly different institute name spellings. `match.py` resolves them
with fuzzy matching:

1. Normalise both name sets: lowercase, collapse whitespace, strip hyphens/commas.
2. For each JoSAA name, call `rapidfuzz.process.extractOne` with `fuzz.token_sort_ratio`
   against the normalised NIRF names.
3. Accept matches scoring ≥ 88 (default threshold in `config.DEFAULT_NAME_MATCH_THRESHOLD`).
4. Build a lookup `josaa_name → (nirf_rank, nirf_score)` used at scoring time.

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

**Atomic writes** — every save writes to a temp file in the same directory, then calls
`os.replace()` to atomically rename it over the target. An interrupted update never
leaves a partially-written file.

**Data directory resolution** — `config.data_dir()` returns `JARS_DATA_DIR` from the
environment if set, otherwise the `data/` directory adjacent to the repository root.
This lets embedding apps redirect to their own data location without code changes.

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
2. Saves the cutoff DataFrame atomically.
3. Derives the NIRF year from the scraped cutoff years (or the `--nirf-year` flag) and
   scrapes NIRF. NIRF failure is non-fatal — existing NIRF data is kept.
4. Writes `meta.json` with updated stats and a UTC timestamp.

Both the CLI and the TUI call this function, passing an optional `progress` callback for
status updates.

---

## TUI Architecture

`tui/jars_tui/app.py` — `RecoApp(App)`:

- **Left panel** (`#form`): a `VerticalScroll` containing labelled `Input` and `Select`
  widgets for all filter parameters.
- **Right panel** (`#results`): a `DataTable` with fixed-width narrow columns and two
  flexible-width columns (Institute, Program) that reflow on terminal resize.

Text wrapping in cells uses `textwrap.wrap()` capped at 6 lines; the `DataTable` row
height is set to the maximum wrapped line count of the two flexible columns.

The live scrape (`action_update`) runs in a `@work(thread=True)` worker to avoid
blocking the event loop. Progress messages are pushed back to the UI thread with
`call_from_thread`.

On startup, if data exists, `action_recommend()` fires automatically so the table is
populated immediately.
