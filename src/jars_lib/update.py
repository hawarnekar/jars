"""Refresh the offline datasets from the live sources.

Used by both the CLI (`jars-lib update`) and the TUI's "update" action.
"""

from __future__ import annotations

import logging
from typing import Callable

from . import storage
from .config import Paths
from .scrape.nirf import scrape_nirf

log = logging.getLogger("jars_lib.update")

ProgressFn = Callable[[str], None]

# "playwright" drives a real browser (works against the protected archive endpoint);
# "httpx" is the lightweight pure-HTTP path (kept for testing — the live endpoint
# currently rejects it, see scrape.josaa).
DEFAULT_BACKEND = "playwright"


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
) -> dict:
    """Scrape JoSAA cutoffs + NIRF rankings and persist them. Returns the new meta."""
    paths = (paths or Paths.resolve()).ensure()

    def say(msg: str) -> None:
        log.info(msg)
        if progress:
            progress(msg)

    say(f"Scraping JoSAA cutoffs (backend: {backend})…")
    df = _scrape_cutoffs(
        backend,
        years,
        rounds,
        institute_types,
        delay=delay,
        headless=headless,
        progress=lambda n: say(f"  …{n} cutoff rows so far"),
    )
    say(f"Fetched {len(df)} cutoff rows. Saving…")
    storage.save_cutoffs(df, paths)

    nirf_year = nirf_year or (int(max(years)) if years else _latest_year(df))
    if nirf_year:
        say(f"Scraping NIRF Engineering {nirf_year}…")
        try:
            scores = scrape_nirf(nirf_year)
            storage.save_nirf(scores, paths)
            say(f"Fetched {len(scores)} NIRF institutes.")
        except Exception as exc:  # noqa: BLE001 — NIRF is best-effort, don't lose cutoffs
            say(f"NIRF scrape failed ({exc}); keeping existing NIRF data.")

    meta = storage.update_meta(
        paths,
        years=sorted({int(y) for y in df["year"].dropna().tolist()}) or years,
        rounds=sorted({int(r) for r in df["round"].dropna().tolist()}) or rounds,
        cutoff_rows=int(len(df)),
        nirf_year=nirf_year,
    )
    say("Done.")
    return meta


def _scrape_cutoffs(backend, years, rounds, institute_types, *, delay, headless, progress):
    """Dispatch to the chosen JoSAA backend."""
    if backend == "playwright":
        from .scrape.josaa_playwright import scrape_cutoffs_playwright

        return scrape_cutoffs_playwright(
            years, rounds, institute_types, headless=headless, progress=progress
        )
    if backend == "httpx":
        from .scrape.josaa import scrape_cutoffs

        return scrape_cutoffs(
            years, rounds, institute_types, delay=delay, progress=progress
        )
    raise ValueError(f"unknown backend {backend!r} (expected 'playwright' or 'httpx')")


def _latest_year(df) -> int | None:
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
        paths, source="demo", cutoff_rows=int(len(df)), years=[2025], rounds=[6]
    )
