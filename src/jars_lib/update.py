"""Refresh the offline datasets from the live sources.

Used by both the CLI (`jars-lib update`) and the TUI's "update" action.
"""

from __future__ import annotations

import logging
from typing import Callable

import pandas as pd

from . import storage
from .config import Paths
from .constants import CUTOFF_COLUMNS
from .scrape.errors import ScrapeError
from .scrape.nirf import scrape_nirf

log = logging.getLogger("jars_lib.update")

ProgressFn = Callable[[str], None]

# "playwright" drives a real browser (works against the protected archive endpoint);
# "httpx" is the lightweight pure-HTTP path (kept for testing — the live endpoint
# currently rejects it, see scrape.josaa).
DEFAULT_BACKEND = "playwright"

# Key columns that identify a unique (year, round, institute_type) combination in the
# cutoffs store, used for resume-mode skip logic.
_RESUME_KEY = ("year", "round", "institute_type")


def update_database(
    *,
    years: list[str] | None = None,
    rounds: list[str] | None = None,
    institute_types: list[str] | None = None,
    nirf_year: int | None = None,
    paths: Paths | None = None,
    delay: float = 0.6,
    backend: str = DEFAULT_BACKEND,
    headless: bool = True,
    progress: ProgressFn | None = None,
    force: bool = False,
    resume: bool = False,
) -> dict:
    """Scrape JoSAA cutoffs + NIRF rankings and persist them. Returns the new meta.

    Parameters
    ----------
    force:
        When ``True``, allow an empty scrape result to overwrite the existing store.
        Default ``False`` (the guard raises :exc:`~scrape.errors.ScrapeError` instead).
    resume:
        When ``True``, load the existing store first and skip ``(year, round, type)``
        combinations that already have rows. Newly fetched rows are merged with the
        existing data and saved incrementally after each (year, round) completes.
    """
    paths = (paths or Paths.resolve()).ensure()

    def say(msg: str) -> None:
        log.info(msg)
        if progress:
            progress(msg)

    # Load existing data upfront — needed for both the empty-overwrite guard and resume.
    existing = storage.load_cutoffs(paths)

    # Compute the set of (year, round, type) tuples already present so the Playwright
    # scraper can skip them in resume mode.
    skip_done: set[tuple[int, int, str]] = set()
    if resume and not existing.empty:
        skip_done = {
            (int(y), int(r), str(t))
            for y, r, t in existing[list(_RESUME_KEY)]
            .dropna()
            .drop_duplicates()
            .itertuples(index=False, name=None)
        }
        say(f"Resume mode: {len(skip_done)} (year, round, type) combinations already in store — skipping.")

    # Accumulated new rows from this run (list of per-round lists, flattened on demand).
    _new_rows: list[dict] = []

    def checkpoint(round_rows: list[dict]) -> None:
        """Called after each (year, round) completes; merges with existing and saves."""
        _new_rows.extend(round_rows)
        partial = pd.DataFrame(_new_rows, columns=list(CUTOFF_COLUMNS))
        if resume and not existing.empty:
            to_save = pd.concat([existing, partial], ignore_index=True)
        else:
            to_save = partial
        storage.save_cutoffs(to_save, paths)
        say(f"  …checkpoint: {len(to_save)} total rows saved.")

    say(f"Scraping JoSAA cutoffs (backend: {backend})…")
    df = _scrape_cutoffs(
        backend,
        years,
        rounds,
        institute_types,
        delay=delay,
        headless=headless,
        progress=lambda n: say(f"  …{n} cutoff rows so far"),
        checkpoint_fn=checkpoint,
        skip_done=skip_done,
    )

    # Empty-overwrite guard: refuse to clobber a populated store with nothing unless
    # the caller explicitly passed --force.
    if df.empty and not existing.empty and not force and not resume:
        raise ScrapeError(
            f"Scrape produced 0 rows; refusing to overwrite the existing "
            f"{len(existing)} rows. Re-run with --force to override, or use "
            "--resume to extend the existing dataset."
        )

    say(f"Fetched {len(df)} new cutoff rows. Saving final result…")
    if resume and not existing.empty:
        # Merge: existing rows + all new rows.  No overlap because skip_done excluded
        # (year, round, type) combos already present.
        final_df = pd.concat([existing, df], ignore_index=True)
    else:
        final_df = df
    storage.save_cutoffs(final_df, paths)

    nirf_year = nirf_year or (int(max(years)) if years else _latest_year(final_df))
    if nirf_year:
        say(f"Scraping NIRF Engineering {nirf_year}…")
        try:
            scores = scrape_nirf(nirf_year)
            storage.save_nirf(scores, paths)
            say(f"Fetched {len(scores)} NIRF institutes.")
        except Exception as exc:  # noqa: BLE001 — NIRF is best-effort, don't lose cutoffs
            log.exception("NIRF scrape failed; keeping existing NIRF data.")
            say(f"NIRF scrape failed ({exc}); keeping existing NIRF data.")

    meta = storage.update_meta(
        paths,
        years=sorted({int(y) for y in final_df["year"].dropna().tolist()}) or years,
        rounds=sorted({int(r) for r in final_df["round"].dropna().tolist()}) or rounds,
        cutoff_rows=int(len(final_df)),
        round_counts=_round_counts(final_df),
        nirf_year=nirf_year,
    )
    say("Done.")
    return meta


def _round_counts(df: pd.DataFrame) -> dict[str, int]:
    """Per-(year, round) row counts, keyed ``"year/round"``.

    Recorded in meta.json so a thin partial slice (e.g. a single freshly-scraped round of
    a new year) is visible rather than silently shadowing a complete prior year.
    """
    if df.empty:
        return {}
    counts: dict[str, int] = {}
    grp = df.dropna(subset=["year", "round"]).groupby(["year", "round"]).size()
    for (year, round_), n in grp.items():
        counts[f"{int(year)}/{int(round_)}"] = int(n)
    return counts


def _scrape_cutoffs(backend, years, rounds, institute_types, *, delay, headless,
                    progress, checkpoint_fn, skip_done):
    """Dispatch to the chosen JoSAA backend."""
    if backend == "playwright":
        from .scrape.josaa_playwright import scrape_cutoffs_playwright

        return scrape_cutoffs_playwright(
            years, rounds, institute_types,
            headless=headless,
            progress=progress,
            checkpoint_fn=checkpoint_fn,
            skip_done=skip_done,
        )
    if backend == "httpx":
        from .scrape.josaa import scrape_cutoffs

        return scrape_cutoffs(
            years, rounds, institute_types, delay=delay, progress=progress
        )
    raise ValueError(f"unknown backend {backend!r} (expected 'playwright' or 'httpx')")


def _latest_year(df: pd.DataFrame) -> int | None:
    vals = df["year"].dropna()
    return int(vals.max()) if len(vals) else None


def seed_demo(paths: Paths | None = None) -> dict:
    """Populate the store with the bundled demo dataset (no network)."""
    from .fixtures import cutoffs_df, nirf_scores

    paths = (paths or Paths.resolve()).ensure()
    df = cutoffs_df()
    storage.save_cutoffs(df, paths)
    storage.save_nirf(nirf_scores(), paths)
    return storage.update_meta(
        paths,
        source="demo",
        cutoff_rows=int(len(df)),
        years=[2025],
        rounds=[6],
        round_counts=_round_counts(df),
    )
