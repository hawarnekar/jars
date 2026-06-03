"""Playwright (headless-browser) backend for the JoSAA archive scrape.

The archive endpoint rejects pure-HTTP postbacks (it 302s to its error page — see
:mod:`josaa`), so the reliable path is to drive the page in a real browser: select the
cascading dropdowns, let the ASP.NET autopostbacks fire, then read the rendered result
table. We reuse :func:`josaa.parse_result_table` to parse that HTML, so the parsing logic
is shared and unit-tested.

The dropdowns use the jQuery "Chosen" plugin, which hides the native ``<select>``. Rather
than fight Chosen's widget, we set the native select's value and dispatch a ``change``
event in-page, which triggers the same ``__doPostBack`` the user would. Selects are
discovered by keyword (id/name substring), mirroring the httpx backend.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pandas as pd

from ..constants import CUTOFF_COLUMNS
from .errors import ScrapeError
from .josaa import (
    ARCHIVE_URL,
    _ALL_OPTION,
    _canonical_type,
    _rank_to_int,
    parse_result_table,
)

log = logging.getLogger("jars_lib.scrape.josaa_playwright")

# JS that sets a native <select> value and fires change (triggers __doPostBack).
_SET_AND_CHANGE = """
(el, value) => {
    el.value = value;
    el.dispatchEvent(new Event('change', { bubbles: true }));
}
"""


def _import_playwright():
    try:
        from playwright.sync_api import TimeoutError as PWTimeout
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ScrapeError(
            "The Playwright backend needs the 'scrape' extra. Install it with:\n"
            "  pip install -e '.[scrape]'\n"
            "  playwright install chromium"
        ) from exc
    return sync_playwright, PWTimeout


class PlaywrightJosaaScraper:
    """Drives the cascading archive form in a headless browser."""

    def __init__(self, *, headless: bool = True, nav_timeout_ms: int = 45_000) -> None:
        self.headless = headless
        self.nav_timeout_ms = nav_timeout_ms
        self._sync_playwright, self._PWTimeout = _import_playwright()

    # -- in-page helpers ----------------------------------------------------

    @staticmethod
    def _discover_selects(page) -> list[dict]:
        """Return [{id, name, autopostback, options:[(value,text)]}] for each select."""
        return page.eval_on_selector_all(
            "select",
            """els => els.map(e => ({
                id: e.id,
                name: e.name,
                autopostback: (e.getAttribute('onchange') || '').includes('doPostBack'),
                options: Array.from(e.options).map(o => [o.value, o.text.trim()])
            }))""",
        )

    @staticmethod
    def _find(selects: list[dict], *keywords: str) -> dict | None:
        kws = [k.lower() for k in keywords]
        for sel in selects:
            hay = f"{sel.get('id', '')} {sel.get('name', '')}".lower()
            if all(k in hay for k in kws):
                return sel
        return None

    @staticmethod
    def _real_options(sel: dict) -> list[tuple[str, str]]:
        """Iterable options: drop the placeholder and the 'ALL' aggregate.

        The Year/Round/Type dimensions are iterated one value at a time; the 'ALL'
        aggregate is excluded so we don't double-count it against the specific values.
        ('ALL' is used deliberately on the Institute/Branch/Seat dropdowns instead.)
        """
        out = []
        for value, text in sel["options"]:
            if (
                value in ("", "0")
                or value.upper() == "ALL"
                or "select" in text.lower()
                or text.strip() in ("", "--")
            ):
                continue
            out.append((value, text))
        return out

    def _find_button(self, page) -> str | None:
        """Return a CSS selector for the submit button (prefer its stable id)."""
        buttons = page.eval_on_selector_all(
            "input[type=submit], input[type=button], button",
            "els => els.map(e => ({id: e.id, name: e.name || '', value: e.value || ''}))",
        )

        def selector(b: dict) -> str | None:
            if b["id"]:
                return f"#{b['id']}"
            if b["name"]:
                return f'[name="{b["name"]}"]'
            return None

        for b in buttons:
            hay = f"{b['id']} {b['name']}".lower()
            if any(k in hay for k in ("btnsubmit", "btnsearch", "submit", "search", "show")):
                if sel := selector(b):
                    return sel
        for b in buttons:
            if sel := selector(b):
                return sel
        return None

    def _select(self, page, select_id: str, value: str, *, autopostback: bool) -> None:
        """Set a dropdown value; wait for the postback navigation if it triggers one."""
        sel = f"#{select_id}"
        if autopostback:
            try:
                with page.expect_navigation(wait_until="load", timeout=self.nav_timeout_ms):
                    page.eval_on_selector(sel, _SET_AND_CHANGE, value)
            except self._PWTimeout:
                # No navigation fired (value unchanged or not autopostback after all).
                page.eval_on_selector(sel, _SET_AND_CHANGE, value)
        else:
            page.eval_on_selector(sel, _SET_AND_CHANGE, value)

    def _select_all_if_present(self, page, *keywords: str) -> None:
        """Select the 'ALL' option on a dropdown if it exists."""
        sel = self._find(self._discover_selects(page), *keywords)
        if not sel:
            return
        for value, text in sel["options"]:
            if _ALL_OPTION.match(text.strip()):
                self._select(page, sel["id"], value, autopostback=sel["autopostback"])
                return

    # -- crawl --------------------------------------------------------------

    def crawl(
        self,
        years: list[str] | None = None,
        rounds: list[str] | None = None,
        institute_types: list[str] | None = None,
        *,
        progress=None,
    ) -> Iterator[dict]:
        sync_playwright = self._sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            try:
                page = browser.new_page()
                page.set_default_timeout(self.nav_timeout_ms)
                page.goto(ARCHIVE_URL, wait_until="load")

                selects = self._discover_selects(page)
                year_sel = self._find(selects, "year")
                if not year_sel:
                    raise ScrapeError("could not locate the Year dropdown on the JoSAA page")

                year_opts = self._real_options(year_sel)
                if years:
                    year_opts = [(v, t) for v, t in year_opts if v in years or t in years]

                for yv, yt in year_opts:
                    self._select(page, year_sel["id"], yv, autopostback=year_sel["autopostback"])
                    yield from self._crawl_year(page, yv, yt, rounds, institute_types, progress)
            finally:
                browser.close()

    def _crawl_year(self, page, yv, yt, rounds, institute_types, progress):
        round_sel = self._find(self._discover_selects(page), "round")
        if not round_sel:
            log.warning("no round dropdown for year %s", yt)
            return
        round_opts = self._real_options(round_sel)
        if rounds:
            round_opts = [(v, t) for v, t in round_opts if v in rounds or t in rounds]

        for rv, rt in round_opts:
            self._select(page, round_sel["id"], rv, autopostback=round_sel["autopostback"])
            type_sel = self._find(self._discover_selects(page), "type")
            if not type_sel:
                log.warning("no institute-type dropdown for %s/%s", yt, rt)
                continue
            type_opts = self._real_options(type_sel)
            if institute_types:
                # Match against the canonical family (IIT/NIT/IIIT/GFTI) since the site's
                # option values are CFI/3IT/etc.
                wanted = {x.upper() for x in institute_types}
                type_opts = [
                    (v, t)
                    for v, t in type_opts
                    if _canonical_type(t).upper() in wanted or v.upper() in wanted
                ]
            for tv, tt in type_opts:
                self._select(page, type_sel["id"], tv, autopostback=type_sel["autopostback"])
                yield from self._crawl_leaf(page, yt, rt, tt, progress)

    def _crawl_leaf(self, page, year, round, inst_type, progress):
        # Choose "All" on the remaining dropdowns where available.
        for keywords in (("institute",), ("branch",), ("seat",)):
            self._select_all_if_present(page, *keywords)

        button_selector = self._find_button(page)
        if not button_selector:
            log.warning("no submit button for %s/%s/%s", year, round, inst_type)
            return
        try:
            with page.expect_navigation(wait_until="load", timeout=self.nav_timeout_ms):
                page.click(button_selector)
        except self._PWTimeout:
            pass  # some result renders without a full navigation

        yr = _rank_to_int(year) or 0
        rd = _rank_to_int(round) or 0
        rows = parse_result_table(
            page.content(), year=yr, round=rd, institute_type=_canonical_type(inst_type)
        )
        log.info("%s/%s/%s -> %d rows", year, round, inst_type, len(rows))
        if progress:
            progress(len(rows))
        yield from rows


def scrape_cutoffs_playwright(
    years: list[str] | None = None,
    rounds: list[str] | None = None,
    institute_types: list[str] | None = None,
    *,
    headless: bool = True,
    progress=None,
) -> pd.DataFrame:
    """Crawl the archive with a headless browser and return a cutoffs DataFrame."""
    scraper = PlaywrightJosaaScraper(headless=headless)
    rows: list[dict] = []

    def leaf_progress(_n: int) -> None:
        if progress:
            progress(len(rows))

    for row in scraper.crawl(years, rounds, institute_types, progress=leaf_progress):
        rows.append(row)
    return pd.DataFrame(rows, columns=list(CUTOFF_COLUMNS))
