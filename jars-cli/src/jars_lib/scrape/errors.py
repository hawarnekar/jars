"""Scraper error types."""

from __future__ import annotations


class ScrapeError(RuntimeError):
    """Raised when a source page can't be driven/parsed as expected.

    Carries a human-actionable message; callers (CLI/TUI) should surface ``str(exc)``
    rather than a traceback.
    """
