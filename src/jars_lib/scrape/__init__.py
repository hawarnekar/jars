"""Scrapers that populate the offline datasets from JoSAA and NIRF."""

from __future__ import annotations

from .aspform import AspForm, parse_form
from .errors import ScrapeError

__all__ = ["AspForm", "parse_form", "ScrapeError"]
