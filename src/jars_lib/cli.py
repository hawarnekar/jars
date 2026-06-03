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

from .config import DEFAULT_ALPHA, Paths
from .constants import GENDER_FEMALE, GENDER_NEUTRAL
from .engine import load_data
from .scrape.errors import ScrapeError
from .update import seed_demo, update_database


def _split(values: str | None) -> list[str] | None:
    if not values:
        return None
    return [v.strip() for v in values.split(",") if v.strip()]


def cmd_recommend(args: argparse.Namespace) -> int:
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
        institute_types=set(_split(args.types) or []) or None,
        year=args.year,
        round=args.round,
        alpha=args.alpha,
        limit=args.limit,
    )
    if not recs:
        print("No programs matched your filters/window.")
        return 0

    _print_table(recs)
    return 0


def _rank_label(itype: str) -> str:
    return "Adv" if itype == "IIT" else "Mains"


def _print_table(recs) -> None:
    headers = ["#", "Type", "Rank", "Institute", "Program", "Cat", "Quota", "Open", "Close", "NIRF", "Feas", "Score"]
    rows = []
    for i, r in enumerate(recs, 1):
        c = r.cutoff
        rows.append(
            [
                str(i),
                c.institute_type,
                _rank_label(c.institute_type),
                _trim(c.institute_name, 38),
                _trim(c.program_name, 34),
                c.seat_type,
                c.quota,
                str(c.opening_rank or "-"),
                str(c.closing_rank or "-"),
                str(r.nirf_rank or "-"),
                f"{r.feasibility:.2f}",
                f"{r.score:.3f}",
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
    try:
        update_database(
            years=_split(args.years),
            rounds=_split(args.rounds),
            institute_types=_split(args.types),
            nirf_year=args.nirf_year,
            delay=args.delay,
            backend=args.backend,
            headless=not args.show_browser,
            progress=lambda msg: print(msg),
        )
    except ScrapeError as exc:
        print(f"\nUpdate failed: {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"\nUpdate failed: network error talking to the source: {exc}", file=sys.stderr)
        return 1
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
    if engine.meta:
        print(f"Meta     : {engine.meta}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jars-lib", description="JEE admission recommender")
    p.add_argument("-v", "--verbose", action="store_true", help="enable info logging")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("recommend", help="print ranked suggestions")
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
    r.add_argument("--alpha", type=float, default=DEFAULT_ALPHA, help="feasibility vs NIRF (0..1)")
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
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
