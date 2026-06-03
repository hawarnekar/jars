"""Textual TUI for the JEE admission recommender.

Layout: an input form (rank, +/- range, category, gender, home state, institute types,
alpha) on the left, a sortable results table on the right. Keys: Enter/`r` to recommend,
`u` to update the database from the web, `q` to quit.
"""

from __future__ import annotations

import textwrap

from jars_lib import load_data
from jars_lib.config import DEFAULT_ALPHA
from jars_lib.constants import GENDER_FEMALE, GENDER_NEUTRAL, INSTITUTE_TYPES, SEAT_TYPES
from jars_lib.engine import RecoEngine
from jars_lib.update import update_database

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Switch,
)

# Fixed-width columns (label, width). Institute & Program are sized dynamically from the
# remaining table width and wrap onto multiple lines when space is tight.
_NARROW_COLUMNS = [
    ("Rank",  5),  # "Adv" or "Mains"
    ("Type",  4),  # "IIT" / "NIT" / …
    ("Cat",  13),  # fits "OBC-NCL (PwD)"
    ("Quota", 6),
    ("Open",  7),
    ("Close", 7),
    ("NIRF",  5),
    ("Feas",  5),
    ("Score", 6),
]

# Bounds for the two flexible text columns.
_MIN_INST, _MIN_PROG = 14, 14
_MAX_INST, _MAX_PROG = 70, 70

# Cap wrapped cell height so one long (dual-degree) name can't dominate the table.
_MAX_WRAP_LINES = 6


def _wrap_cell(text: str, width: int) -> list[str]:
    """Wrap text to ``width``, capped at _MAX_WRAP_LINES lines (ellipsising the last)."""
    lines = textwrap.wrap(text, width) or [""]
    if len(lines) > _MAX_WRAP_LINES:
        lines = lines[:_MAX_WRAP_LINES]
        lines[-1] = lines[-1][: max(1, width - 1)].rstrip() + "…"
    return lines


class RecoApp(App):
    """The recommendation TUI."""

    CSS = """
    #form { width: 38; padding: 1 2; border-right: solid $accent; }
    #form Label { margin-top: 1; color: $text-muted; }
    #results { padding: 0 1; }
    #status { dock: bottom; height: 1; color: $text-muted; padding: 0 1; }
    DataTable { height: 1fr; }
    .row { height: auto; }
    Switch { width: auto; }
    """

    BINDINGS = [
        ("r", "recommend", "Recommend"),
        ("u", "update", "Update DB"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.engine: RecoEngine = load_data()
        self._recs: list = []  # last results, kept so we can re-render on resize

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with VerticalScroll(id="form"):
                yield Label("JEE Advanced rank (for IITs)")
                yield Input(placeholder="e.g. 3000  (leave blank if not applicable)", id="adv_rank", type="integer")
                yield Label("JEE Mains rank / CRL (for NITs/IIITs/GFTIs)")
                yield Input(placeholder="e.g. 25000  (leave blank if not applicable)", id="mains_rank", type="integer")
                yield Label("± rank range")
                yield Input(value="2000", id="range", type="integer")
                yield Label("Category (seat type)")
                yield Select(
                    [(s, s) for s in SEAT_TYPES], value="OPEN", id="category", allow_blank=False
                )
                with Horizontal(classes="row"):
                    yield Label("Female-only seats ")
                    yield Switch(id="female")
                yield Label("Home state (optional)")
                yield Input(placeholder="e.g. Rajasthan", id="home_state")
                yield Label("Institute types")
                yield Select(
                    [("All", "ALL")] + [(t, t) for t in INSTITUTE_TYPES],
                    value="ALL",
                    id="types",
                    allow_blank=False,
                )
                yield Label("α  feasibility ↔ NIRF")
                yield Select(
                    [(f"{a:.1f}", a) for a in [0.0, 0.25, 0.5, 0.75, 1.0]],
                    value=DEFAULT_ALPHA,
                    id="alpha",
                    allow_blank=False,
                )
                yield Button("Recommend (r)", id="go", variant="primary")
                yield Button("Update DB (u)", id="upd", variant="warning")
            with Vertical(id="results"):
                yield DataTable(id="table", zebra_stripes=True, cursor_type="row")
        yield Static(self._status_text(), id="status")
        yield Footer()

    def on_mount(self) -> None:
        if self.engine.is_empty:
            self._render([])  # set up columns even with no data
            self.notify(
                "No data loaded. Press 'u' to update, or run `jars-lib seed-demo`.",
                severity="warning",
                timeout=8,
            )
        else:
            self.action_recommend()

    def on_resize(self, event) -> None:
        # Re-flow the flexible columns (and re-wrap text) when the terminal resizes.
        try:
            self._render(self._recs)
        except Exception:  # pragma: no cover - table may not exist yet very early
            pass

    def _status_text(self) -> str:
        meta = self.engine.meta or {}
        if self.engine.is_empty:
            return "No local data. Press 'u' to update from the web."
        return (
            f"Loaded {len(self.engine.cutoffs)} cutoffs · NIRF {len(self.engine.nirf)} · "
            f"last updated {meta.get('last_updated', 'unknown')}"
        )

    # -- actions ------------------------------------------------------------

    @on(Button.Pressed, "#go")
    def _on_go(self) -> None:
        self.action_recommend()

    @on(Button.Pressed, "#upd")
    def _on_upd(self) -> None:
        self.action_update()

    def action_recommend(self) -> None:
        if self.engine.is_empty:
            self.notify("No data — update first (u).", severity="warning")
            return

        def _parse_rank(widget_id: str) -> int | None:
            val = self.query_one(widget_id, Input).value.strip()
            return int(val) if val else None

        try:
            adv_rank = _parse_rank("#adv_rank")
            mains_rank = _parse_rank("#mains_rank")
            rng = int(self.query_one("#range", Input).value or 0)
        except ValueError:
            self.notify("Ranks and range must be integers.", severity="error")
            return

        if adv_rank is None and mains_rank is None:
            self.notify(
                "Enter at least one rank: JEE Advanced (for IITs) or JEE Mains (for NITs/IIITs/GFTIs).",
                severity="warning",
                timeout=6,
            )
            return

        category = self.query_one("#category", Select).value
        female = self.query_one("#female", Switch).value
        home_state = self.query_one("#home_state", Input).value.strip() or None
        types_val = self.query_one("#types", Select).value
        alpha = float(self.query_one("#alpha", Select).value)

        institute_types = None if types_val == "ALL" else {types_val}
        gender = GENDER_FEMALE if female else GENDER_NEUTRAL

        recs = self.engine.recommend(
            rng,
            jee_adv_rank=adv_rank,
            jee_mains_rank=mains_rank,
            seat_type=category,
            gender=gender,
            home_state=home_state,
            institute_types=institute_types,
            alpha=alpha,
            limit=200,
        )
        self._render(recs)
        rank_info = "  ".join(
            p for p in [
                f"Adv {adv_rank}" if adv_rank else "",
                f"Mains {mains_rank}" if mains_rank else "",
            ] if p
        )
        self.query_one("#status", Static).update(
            f"{len(recs)} matches · {rank_info} ±{rng} · {category} · α={alpha}"
        )

    def _column_widths(self) -> tuple[int, int]:
        """Width for the Institute and Program columns from the live table width."""
        table = self.query_one("#table", DataTable)
        avail = table.size.width
        if avail <= 0:  # not laid out yet — estimate from the screen minus the form pane
            avail = max(40, self.size.width - 42)
        pad = (getattr(table, "cell_padding", 1) or 1) * 2
        n_cols = len(_NARROW_COLUMNS) + 2
        overhead = pad * n_cols + 2
        remaining = avail - sum(w for _, w in _NARROW_COLUMNS) - overhead
        remaining = max(remaining, _MIN_INST + _MIN_PROG)
        inst_w = max(_MIN_INST, min(_MAX_INST, int(remaining * 0.55)))
        prog_w = max(_MIN_PROG, min(_MAX_PROG, remaining - inst_w))
        return inst_w, prog_w

    def _render(self, recs) -> None:
        self._recs = recs
        table = self.query_one("#table", DataTable)
        inst_w, prog_w = self._column_widths()

        # Rebuild columns each render so widths track the current terminal size.
        table.clear(columns=True)
        table.add_column("Institute", width=inst_w)
        table.add_column("Program", width=prog_w)
        for label, width in _NARROW_COLUMNS:
            table.add_column(label, width=width)

        for r in recs:
            c = r.cutoff
            rank_type = "Adv" if c.institute_type == "IIT" else "Mains"
            inst_lines = _wrap_cell(c.institute_name, inst_w)
            prog_lines = _wrap_cell(c.program_name, prog_w)
            row_height = max(len(inst_lines), len(prog_lines))
            table.add_row(
                "\n".join(inst_lines),
                "\n".join(prog_lines),
                rank_type,
                c.institute_type,
                c.seat_type,
                c.quota,
                str(c.opening_rank or "-"),
                str(c.closing_rank or "-"),
                str(r.nirf_rank or "-"),
                f"{r.feasibility:.2f}",
                f"{r.score:.3f}",
                height=row_height,
            )

    def action_update(self) -> None:
        self.notify("Updating from JoSAA + NIRF… this can take a while.", timeout=6)
        self._run_update()

    @work(thread=True, exclusive=True)
    def _run_update(self) -> None:
        def progress(msg: str) -> None:
            self.call_from_thread(self.query_one("#status", Static).update, msg)

        try:
            update_database(progress=progress)
        except Exception as exc:  # noqa: BLE001
            self.call_from_thread(
                self.notify, f"Update failed: {exc}", severity="error", timeout=10
            )
            return
        self.engine = load_data()
        self.call_from_thread(self.query_one("#status", Static).update, self._status_text())
        self.call_from_thread(self.notify, "Database updated.", timeout=5)
        self.call_from_thread(self.action_recommend)


def main() -> int:
    RecoApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
