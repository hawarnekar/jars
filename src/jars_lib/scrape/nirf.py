"""Scrape NIRF Engineering rankings into NirfScore records.

NIRF publishes the ranking as an HTML table at
``https://www.nirfindia.org/Rankings/<year>/EngineeringRanking.html``. We parse the
institute name, rank, and score. No official CSV exists, so HTML parsing is the path.
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

from ..models import NirfScore

log = logging.getLogger("jars_lib.scrape.nirf")

NIRF_URL = "https://www.nirfindia.org/Rankings/{year}/EngineeringRanking.html"


# NIRF institute ids look like "IR-E-U-0456" / "IR-E-I-1074". They reliably mark the
# real data rows, letting us skip the interleaved "More Details" breakdown sub-rows.
_ID_RE = re.compile(r"^\s*IR-[A-Z]", re.IGNORECASE)


def parse_nirf_table(html: str, *, year: int) -> list[NirfScore]:
    """Parse the NIRF Engineering ranking HTML into NirfScore records.

    The live table has a 6-column header (Institute ID, Name, City, State, Score, Rank)
    but each data row carries extra hidden "More Details" cells, so column *positions*
    don't line up with the header. We instead key off two stable facts: a data row's
    first cell is an NIRF id, and Score + Rank are always its last two cells.
    """
    soup = BeautifulSoup(html, "lxml")

    for table in soup.find_all("table"):
        header = table.get_text(" ", strip=True).lower()
        if "name" not in header or "rank" not in header or "score" not in header:
            continue

        scores: list[NirfScore] = []
        seen: set[str] = set()
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3 or not _ID_RE.match(cells[0]):
                continue  # header / detail sub-row / non-data row
            name = _clean_name(cells[1])
            score = _to_float(cells[-2])
            rank = _to_int(cells[-1])
            if not name or score is None or rank is None:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            scores.append(
                NirfScore(year=year, institute_name=name, nirf_rank=rank, nirf_score=score)
            )
        if scores:
            log.info("NIRF %s -> %d institutes", year, len(scores))
            return scores

    log.info("NIRF %s -> 0 institutes (no recognised table)", year)
    return []


def _clean_name(text: str) -> str:
    # Names often include a trailing "More Details" / id; trim at common separators.
    text = re.split(r"\s{2,}|\bMore Details\b|\bID:", text)[0]
    return text.strip(" ,")


def _to_float(text: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
    return float(m.group()) if m else None


def _to_int(text: str) -> int | None:
    m = re.search(r"\d+", text.replace(",", ""))
    return int(m.group()) if m else None


def scrape_nirf(year: int, *, timeout: float = 60.0) -> list[NirfScore]:
    """Fetch and parse the NIRF Engineering ranking for ``year``."""
    url = NIRF_URL.format(year=year)
    with httpx.Client(
        timeout=timeout,
        headers={"User-Agent": "jars-lib/0.1 (+offline nirf archive)"},
        follow_redirects=True,
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return parse_nirf_table(resp.text, year=year)
