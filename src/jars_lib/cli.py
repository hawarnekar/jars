"""Headless command-line interface: ``jars-lib <command>``.

Commands:
  recommend   Print ranked suggestions for a rank + window.
  update      Scrape JoSAA + NIRF into the offline store.
  seed-demo   Load the bundled demo dataset (no network).
  info        Show what's in the local store.
"""

from __future__ import annotations

import argparse
import logging
import sys

import httpx

from .config import Paths
from .constants import GENDER_FEMALE, GENDER_NEUTRAL, INSTITUTE_TYPES, SEAT_TYPES
from .engine import load_data
from .scrape.errors import ScrapeError
from .update import seed_demo, update_database


def _split(values: str | None) -> list[str] | None:
    if not values:
        return None
    return [v.strip() for v in values.split(",") if v.strip()]


def cmd_recommend(args: argparse.Namespace) -> int:
    # Input validation — catch bad values before they reach the engine.
    if args.category not in SEAT_TYPES:
        valid = ", ".join(SEAT_TYPES)
        print(f"Error: unknown --category {args.category!r}. Valid values: {valid}.", file=sys.stderr)
        return 2

    types_list = _split(args.types)
    if types_list:
        invalid = [t for t in types_list if t not in INSTITUTE_TYPES]
        if invalid:
            print(
                f"Error: unknown --types value(s): {', '.join(invalid)}. "
                f"Valid values: {', '.join(INSTITUTE_TYPES)}.",
                file=sys.stderr,
            )
            return 2

    engine = load_data()
    if engine.is_empty:
        print(
            "No data yet. Run `jars-lib seed-demo` (demo) or `jars-lib update` (real).",
            file=sys.stderr,
        )
        return 2

    adv_rank: int | None = args.adv_rank
    mains_rank: int | None = args.mains_rank
    if adv_rank is None and mains_rank is None:
        print(
            "Error: provide at least one of --adv-rank (JEE Advanced) or "
            "--mains-rank (JEE Mains).",
            file=sys.stderr,
        )
        return 2

    gender = GENDER_FEMALE if args.female else GENDER_NEUTRAL
    recs = engine.recommend(
        args.range,
        jee_adv_rank=adv_rank,
        jee_mains_rank=mains_rank,
        seat_type=args.category,
        gender=gender,
        home_state=args.home_state,
        institute_types=set(types_list) if types_list else None,
        year=args.year,
        round=args.round,
        limit=args.limit,
    )
    if not recs:
        print("No programs matched your filters/window.")
        return 0

    _print_table(recs)
    return 0


def _fmt_rank_year(value: int | None, year: int | None) -> str:
    """Render a rank with the year it occurred, e.g. ``1 (2024)``."""
    if value is None:
        return "-"
    return f"{value} ({year})" if year is not None else str(value)


def _fmt_years(years, reach: bool = False) -> str:
    """Render a band of years: a bare year, or comma-separated in parentheses if several.

    ``reach=True`` prefixes a ``~`` to flag that these are near-window years the rank did
    not actually clear (so the Open/Close shown explain a low chance, not an assured seat).
    """
    if not years:
        return "-"
    body = str(years[0]) if len(years) == 1 else "(" + ", ".join(str(y) for y in years) + ")"
    return f"~{body}" if reach else body


def _print_table(recs) -> None:
    headers = ["#", "Institute", "Program", "Category", "Quota", "Open", "Close", "Years", "NIRF", "Chance", "Trend"]
    rows = []
    for i, r in enumerate(recs, 1):
        c = r.cutoff
        rows.append(
            [
                str(i),
                _trim(c.institute_name, 38),
                _trim(c.program_name, 34),
                c.seat_type,
                c.quota,
                _fmt_rank_year(r.opening_rank_min, r.opening_rank_min_year),
                _fmt_rank_year(r.closing_rank_max, r.closing_rank_max_year),
                _fmt_years(r.band_years, reach=not r.band_in_range),
                str(r.nirf_rank or "-"),
                f"{r.feasibility * 100:.0f}%",
                r.closing_rank_trend or "-",
            ]
        )
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def _trim(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def cmd_update(args: argparse.Namespace) -> int:
    update_database(
        years=_split(args.years),
        rounds=_split(args.rounds),
        institute_types=_split(args.types),
        nirf_year=args.nirf_year,
        delay=args.delay,
        backend=args.backend,
        headless=not args.show_browser,
        progress=lambda msg: print(msg),
        force=args.force,
        resume=args.resume,
    )
    return 0


def cmd_seed_demo(args: argparse.Namespace) -> int:
    meta = seed_demo()
    print(f"Seeded demo dataset: {meta.get('cutoff_rows')} rows. Try `jars-lib recommend`.")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    paths = Paths.resolve()
    engine = load_data(paths)
    print(f"Data dir : {paths.root}")
    print(f"Cutoffs  : {len(engine.cutoffs)} rows")
    print(f"NIRF     : {len(engine.nirf)} institutes")
    if not engine.is_empty:
        print(f"Years    : {engine.years()}")
    round_counts = engine.meta.get("round_counts") if engine.meta else None
    if round_counts:
        print("Rounds   :")
        for key in sorted(round_counts):
            print(f"  {key:>10}: {round_counts[key]} rows")
    if engine.meta:
        shown = {k: v for k, v in engine.meta.items() if k != "round_counts"}
        print(f"Meta     : {shown}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jars-lib", description="JEE admission recommender")
    p.add_argument("-v", "--verbose", action="store_true", help="enable info logging")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser(
        "recommend",
        help="print ranked suggestions",
        epilog=(
            "If no data is loaded yet, run `jars-lib seed-demo` (bundled demo, no network) "
            "or `jars-lib update` (live JoSAA data) first."
        ),
    )
    r.add_argument(
        "--adv-rank", type=int, default=None, metavar="RANK",
        help="JEE Advanced rank (for IIT recommendations)",
    )
    r.add_argument(
        "--mains-rank", type=int, default=None, metavar="RANK",
        help="JEE Mains rank / CRL (for NIT/IIIT/GFTI recommendations)",
    )
    r.add_argument("--range", type=int, default=2000, help="+/- closing-rank window")
    r.add_argument("--category", default="OPEN", help="seat type, e.g. OPEN, OBC-NCL, SC, ST, EWS")
    r.add_argument("--female", action="store_true", help="include female-only seats")
    r.add_argument("--home-state", default=None, help="enable home-state quota seats (NITs/IIITs/GFTIs)")
    r.add_argument("--types", default=None, help="comma list to restrict: IIT,NIT,IIIT,GFTI")
    r.add_argument("--year", type=int, default=None)
    r.add_argument("--round", type=int, default=None)
    r.add_argument("--limit", type=int, default=30)
    r.set_defaults(func=cmd_recommend)

    u = sub.add_parser("update", help="scrape JoSAA + NIRF into the offline store")
    u.add_argument("--years", default=None, help="comma list of years, default all")
    u.add_argument("--rounds", default=None, help="comma list of rounds, default all")
    u.add_argument("--types", default=None, help="comma list of institute types")
    u.add_argument("--nirf-year", type=int, default=None)
    u.add_argument("--delay", type=float, default=0.6, help="polite delay (httpx backend)")
    u.add_argument(
        "--backend",
        choices=("playwright", "httpx"),
        default="playwright",
        help="scrape backend (default: playwright headless browser)",
    )
    u.add_argument(
        "--show-browser",
        action="store_true",
        help="run Playwright with a visible browser window (debugging)",
    )
    u.add_argument(
        "--force",
        action="store_true",
        help="allow an empty scrape result to overwrite the existing store",
    )
    u.add_argument(
        "--resume",
        action="store_true",
        help="skip (year, round, type) combinations already in the store and merge new rows",
    )
    u.set_defaults(func=cmd_update)

    s = sub.add_parser("seed-demo", help="load the bundled demo dataset (no network)")
    s.set_defaults(func=cmd_seed_demo)

    i = sub.add_parser("info", help="show local store status")
    i.set_defaults(func=cmd_info)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )
    try:
        return args.func(args)
    except ScrapeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"\nError: network error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
