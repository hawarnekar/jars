# jars — JEE Admission Recommendation System

Recommends engineering colleges and programs based on your JEE rank. Uses historical
JoSAA opening/closing ranks (IITs, NITs, IIITs, GFTIs) and NIRF Engineering rankings,
all stored locally for offline use.

---

## Requirements

- Python 3.10 or later
- macOS, Linux, or Windows (WSL)

---

## Install

**1. Clone the repository**

```bash
git clone <repo-url> jars
cd jars
```

**2. Create and activate a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows PowerShell
```

**3. Install the package**

```bash
# Full install (library + TUI + live scraper + dev tools):
pip install -e ".[all]"

# Minimal install (library + TUI only, no live scraping):
pip install -e ".[tui]"
```

**4. (Optional) Install the Playwright browser for live data fetching**

Only needed if you want to download fresh JoSAA data from the web:

```bash
playwright install chromium
```

---

## Quick Start

### Try it immediately with the bundled demo data (no network required)

```bash
jars-lib seed-demo
jars-lib recommend --mains-rank 25000
```

### Launch the interactive terminal UI

```bash
jars
```

### Get recommendations from the command line

```bash
# NIT/IIIT/GFTI results using JEE Mains rank:
jars-lib recommend --mains-rank 25000 --range 5000 --category OBC-NCL

# IIT results using JEE Advanced rank:
jars-lib recommend --adv-rank 3000 --range 1000

# Both IIT and non-IIT results together:
jars-lib recommend --adv-rank 3000 --mains-rank 25000 --range 2000

# Restrict to NITs only, include female-only seats, apply home-state quota:
jars-lib recommend --mains-rank 25000 --types NIT --female --home-state Rajasthan

# Adjust the alpha weight (0 = favour NIRF rank, 1 = favour safest admit):
jars-lib recommend --mains-rank 25000 --alpha 0.3
```

### Download real JoSAA data from the web

```bash
# All years, all rounds (long — hundreds of postbacks):
jars-lib update

# A fast slice: 2024, round 1, IITs only (~10 seconds):
jars-lib update --years 2024 --rounds 1 --types IIT

# Watch the browser window while it scrapes:
jars-lib update --years 2024 --show-browser
```

### Check what is stored locally

```bash
jars-lib info
```

---

## CLI Reference

### `jars-lib recommend`

| Flag | Default | Description |
|---|---|---|
| `--adv-rank RANK` | — | JEE Advanced rank (IIT seats) |
| `--mains-rank RANK` | — | JEE Mains / CRL rank (NIT/IIIT/GFTI seats) |
| `--range N` | 2000 | ± window around your rank to search |
| `--category CAT` | OPEN | Seat type: `OPEN`, `OBC-NCL`, `SC`, `ST`, `EWS` (append `(PwD)` for PwD variants) |
| `--female` | off | Include female-only seats |
| `--home-state STATE` | — | Enable home-state quota seats at NITs/IIITs/GFTIs |
| `--types LIST` | all | Comma-separated filter: `IIT`, `NIT`, `IIIT`, `GFTI` |
| `--year Y` | latest | Data year to use |
| `--round R` | latest | Counselling round to use |
| `--alpha A` | 0.5 | Scoring weight: 0 = NIRF quality only, 1 = safety only |
| `--limit N` | 30 | Maximum results to print |

### `jars-lib update`

| Flag | Default | Description |
|---|---|---|
| `--years LIST` | all | Comma-separated years, e.g. `2024,2023` |
| `--rounds LIST` | all | Comma-separated rounds, e.g. `1,6` |
| `--types LIST` | all | Institute types to fetch |
| `--nirf-year Y` | latest year found | NIRF ranking year to fetch |
| `--backend` | `playwright` | `playwright` (headless browser) or `httpx` (plain HTTP, currently server-blocked) |
| `--show-browser` | off | Open a visible browser window (useful for debugging) |
| `--delay N` | 0.6 | Seconds between requests (httpx backend only) |

### `jars-lib seed-demo`

Loads the bundled offline dataset — no network access needed. Useful for testing and demos.

### `jars-lib info`

Prints the data directory path, row counts, and last-updated timestamp.

---

## Data Directory

Data is stored under `data/` in the repository root by default:

```
data/
  cutoffs.parquet         JoSAA opening/closing ranks
  nirf_engineering.json   NIRF Engineering institute scores
  meta.json               Metadata (last updated, row counts)
```

Override the location with the `JARS_DATA_DIR` environment variable:

```bash
JARS_DATA_DIR=/path/to/my/data jars-lib recommend --mains-rank 25000
```

---

## Run Tests

```bash
pip install -e ".[dev]"
pytest
```

---

## Notes

- Cutoff data reflects the previous year's results — use as a guide, not a guarantee.
- Home-state quota seats are shown only when `--home-state` is supplied.
- NIRF covers the Engineering list only; institutes not in NIRF are scored on feasibility alone.
- A full multi-year scrape can take many minutes. Scope it with `--years`/`--rounds`/`--types`.
- The live JoSAA scrape requires Playwright because the archive endpoint rejects plain HTTP form posts.
