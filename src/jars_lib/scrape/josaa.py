"""Scrape the JoSAA opening/closing-rank archive into a tidy cutoffs DataFrame.

The page (``openingclosingrankarchieve.aspx``) is an ASP.NET WebForms form with cascading
dropdowns: Year -> Round -> Institute Type -> Institute -> Program -> Seat Type, plus a
"Submit" button that renders a result table. We drive it with :mod:`aspform`, posting back
as a browser would, then parse the result table.

Selectors are discovered by keyword (``find_select("year")`` etc.) rather than hard-coded
control ids, so minor markup changes don't break the crawl.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterator

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from ..constants import CUTOFF_COLUMNS
from .aspform import AspForm, parse_form
from .errors import ScrapeError
from .retry import with_retry

log = logging.getLogger("jars_lib.scrape.josaa")

# ASP.NET customErrors redirects unhandled exceptions here; treat as a hard failure.
_ERROR_PATH_MARKERS = ("errmsg.aspx", "aspxerrorpath")
_ERROR_TEXT_MARKERS = ("something went wrong", "error message")

ARCHIVE_URL = (
    "https://josaa.admissions.nic.in/applicant/seatmatrix/"
    "openingclosingrankarchieve.aspx"
)

# Header text -> canonical column. Matching is case-insensitive substring.
_HEADER_MAP = (
    ("institute", "institute_name"),
    ("academic program", "program_name"),
    ("program", "program_name"),
    ("quota", "quota"),
    ("seat type", "seat_type"),
    ("gender", "gender"),
    ("opening", "opening_rank"),
    ("closing", "closing_rank"),
)

_ALL_OPTION = re.compile(r"^all\b", re.IGNORECASE)


def _rank_to_int(text: str) -> int | None:
    """JoSAA writes ranks like '1234' or '1234P' (preparatory). Keep the digits."""
    if not text:
        return None
    m = re.search(r"\d+", text.replace(",", ""))
    return int(m.group()) if m else None


def parse_result_table(
    html: str, *, year: int, round: int, institute_type: str
) -> list[dict]:
    """Parse a rendered result table into cutoff row dicts."""
    soup = BeautifulSoup(html, "lxml")
    table = None
    # Pick the widest table that has both 'institute' and 'closing' in its header.
    for cand in soup.find_all("table"):
        header_text = cand.get_text(" ", strip=True).lower()
        if "institute" in header_text and "closing" in header_text:
            table = cand
            break
    if table is None:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    # Locate header row + build column index map.
    header_cells = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
    col_index: dict[str, int] = {}
    for i, htext in enumerate(header_cells):
        low = htext.lower()
        for needle, canon in _HEADER_MAP:
            if needle in low and canon not in col_index:
                col_index[canon] = i

    required = {"institute_name", "program_name", "closing_rank"}
    if not required.issubset(col_index):
        return []

    out: list[dict] = []
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < len(header_cells):
            continue

        def cell(canon: str) -> str:
            idx = col_index.get(canon)
            text = cells[idx] if idx is not None and idx < len(cells) else ""
            return re.sub(r"\s+", " ", text).strip()  # source has stray double spaces

        out.append(
            dict(
                year=year,
                round=round,
                institute_type=institute_type,
                institute_name=cell("institute_name"),
                program_name=cell("program_name"),
                quota=cell("quota") or "AI",
                seat_type=cell("seat_type"),
                gender=cell("gender"),
                opening_rank=_rank_to_int(cell("opening_rank")),
                closing_rank=_rank_to_int(cell("closing_rank")),
            )
        )
    return out


class JosaaClient:
    """Drives the cascading form to extract cutoffs.

    Strategy: for each Year x Round x Institute Type, select the "All" option in the
    Institute / Program / Seat Type dropdowns where available and submit, yielding one big
    table per (year, round, type). This minimises postbacks versus iterating every
    institute individually. Falls back gracefully if "All" is unavailable.
    """

    def __init__(self, *, delay: float = 0.6, timeout: float = 60.0) -> None:
        self.delay = delay
        # Count of (year, round, type) leaves skipped because no submit button could be
        # identified — surfaced to the caller at the end of a crawl.
        self.skipped_leaves = 0
        self.client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "jars-lib/0.1 (+offline cutoff archive)"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "JosaaClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- low-level postback helpers ----------------------------------------

    def _get_form(self) -> AspForm:
        def do() -> httpx.Response:
            resp = self.client.get(ARCHIVE_URL)
            resp.raise_for_status()
            return resp

        resp = with_retry(do, description="loading the archive page")
        self._check_error(resp, context="loading the archive page")
        return self._parse(resp)

    def _post(self, form: AspForm, payload: dict[str, str]) -> tuple[AspForm, str]:
        time.sleep(self.delay)

        def do() -> httpx.Response:
            resp = self.client.post(ARCHIVE_URL, data=payload)
            resp.raise_for_status()
            return resp

        resp = with_retry(do, description="submitting a form postback")
        self._check_error(resp, context="submitting a form postback")
        return self._parse(resp), resp.text

    @staticmethod
    def _check_error(resp: httpx.Response, *, context: str) -> None:
        """Detect ASP.NET's customErrors redirect / error page and fail clearly."""
        url = str(resp.url).lower()
        redirected = any(
            any(m in str(h.headers.get("location", "")).lower() for m in _ERROR_PATH_MARKERS)
            for h in resp.history
        )
        if any(m in url for m in _ERROR_PATH_MARKERS) or redirected:
            raise ScrapeError(
                "The JoSAA archive server rejected the request while "
                f"{context}: it redirected every form submission to its error page "
                "(ErrMsg.aspx). The opening/closing-rank archive endpoint is not "
                "accepting automated postbacks right now (anti-automation or a "
                "temporary server fault). Try again later, or scrape via a real "
                "browser (Playwright). Meanwhile, `jars-lib seed-demo` loads offline "
                "demo data."
            )
        low = resp.text[:2000].lower()
        if "<form" not in resp.text.lower() and any(m in low for m in _ERROR_TEXT_MARKERS):
            raise ScrapeError(
                f"The JoSAA archive returned an error page while {context}. "
                "The endpoint may be temporarily unavailable; try again later."
            )

    @staticmethod
    def _parse(resp: httpx.Response) -> AspForm:
        try:
            return parse_form(resp.text)
        except ValueError as exc:
            raise ScrapeError(
                f"Unexpected JoSAA response (no form found): {exc}. The page layout "
                "may have changed."
            ) from exc

    def _select_all_value(self, form: AspForm, *keywords: str) -> tuple[str, str] | None:
        """Return (select_name, value) for an 'ALL' option, if the dropdown exists."""
        sel = form.find_select(*keywords)
        if not sel:
            return None
        for value, text in sel.options:
            if _ALL_OPTION.match(text.strip()):
                return sel.name, value
        return None

    # -- public API ---------------------------------------------------------

    def list_years(self) -> list[str]:
        return [v for v, _ in self._get_form().options("year")]

    def crawl(
        self,
        years: list[str] | None = None,
        rounds: list[str] | None = None,
        institute_types: list[str] | None = None,
    ) -> Iterator[dict]:
        """Yield cutoff row dicts across the requested cross-product.

        ``None`` for any axis means "all available options" discovered from the live form.
        """
        form = self._get_form()
        year_sel = form.find_select("year")
        if not year_sel:
            raise RuntimeError("could not locate the Year dropdown on the JoSAA page")
        year_name = year_sel.name

        year_opts = form.options("year")
        if years:
            year_opts = [(v, t) for v, t in year_opts if v in years or t in years]

        for yv, yt in year_opts:
            form, _ = self._post(form, form.postback(year_name, yv))
            round_sel = form.find_select("round")
            if not round_sel:
                log.warning("no round dropdown for year %s", yt)
                continue
            round_opts = form.options("round")
            if rounds:
                round_opts = [(v, t) for v, t in round_opts if v in rounds or t in rounds]

            for rv, rt in round_opts:
                form, _ = self._post(form, form.postback(round_sel.name, rv))
                type_sel = form.find_select("type")
                if not type_sel:
                    log.warning("no institute-type dropdown for %s/%s", yt, rt)
                    continue
                type_opts = form.options("type")
                if institute_types:
                    type_opts = [
                        (v, t)
                        for v, t in type_opts
                        if v in institute_types or t in institute_types
                    ]

                for tv, tt in type_opts:
                    form, _ = self._post(form, form.postback(type_sel.name, tv))
                    yield from self._crawl_leaf(form, yt, rt, tt)

    def _crawl_leaf(self, form: AspForm, year: str, round: str, inst_type: str):
        """Select 'All' on the remaining dropdowns, submit, and parse the table."""
        # Set institute/program/seat-type to "All" where present.
        for keywords in (("institute",), ("program",), ("seat",)):
            picked = self._select_all_value(form, *keywords)
            if picked:
                name, value = picked
                form, _ = self._post(form, form.postback(name, value))

        # Find and click the submit/search button. If none can be identified we skip the
        # leaf rather than guess: clicking an unrelated control would parse as zero rows
        # (or worse, the wrong table) and silently corrupt the result.
        button_name = self._find_button(form)
        if not button_name:
            self.skipped_leaves += 1
            log.warning(
                "no submit button identified for %s/%s/%s — skipping this leaf",
                year, round, inst_type,
            )
            return
        _, html = self._post(form, form.submit(button_name))

        yr = _rank_to_int(year) or 0
        rd = _rank_to_int(round) or 0
        rows = parse_result_table(
            html, year=yr, round=rd, institute_type=_canonical_type(inst_type)
        )
        log.info("%s/%s/%s -> %d rows", year, round, inst_type, len(rows))
        yield from rows

    @staticmethod
    def _find_button(form: AspForm) -> str | None:
        """Return the submit button's control name, or None if no keyword matches.

        We deliberately do *not* fall back to "the first button": on a WebForms page that
        could be an unrelated control, yielding an empty/wrong table parsed as zero rows.
        Returning None makes the caller skip the leaf instead.
        """
        names = list(form.buttons) or list(form.base_payload())
        for name in names:
            low = name.lower()
            if any(k in low for k in ("btnsubmit", "btnsearch", "submit", "search", "show")):
                return name
        return None


def _canonical_type(text: str) -> str:
    low = text.lower()
    if "indian institute of technology" in low or low.strip() == "iit":
        return "IIT"
    if "national institute of technology" in low or "nit" in low:
        return "NIT"
    if "information technology" in low or "iiit" in low:
        return "IIIT"
    return "GFTI"


def scrape_cutoffs(
    years: list[str] | None = None,
    rounds: list[str] | None = None,
    institute_types: list[str] | None = None,
    *,
    delay: float = 0.6,
    progress=None,
) -> pd.DataFrame:
    """Crawl the archive and return a cutoffs DataFrame.

    ``progress`` is an optional callable ``(rows_so_far) -> None`` for UI updates.
    """
    rows: list[dict] = []
    with JosaaClient(delay=delay) as client:
        for row in client.crawl(years, rounds, institute_types):
            rows.append(row)
            if progress and len(rows) % 200 == 0:
                progress(len(rows))
        if client.skipped_leaves:
            log.warning(
                "%d (year, round, type) leaf/leaves were skipped (no submit button "
                "identified); their rows are absent from this scrape.",
                client.skipped_leaves,
            )
    df = pd.DataFrame(rows, columns=list(CUTOFF_COLUMNS))
    return df
