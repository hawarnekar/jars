"""The recommendation engine — the core reusable API.

Given a candidate's rank and a +/- window, plus their category/gender/state and an
institute-type filter, it summarises each matching program *across all available years*
and ranks the resulting (institute, program) pairs.

**Ranking.** Each pair gets a single ``score`` in [0, 1] (higher is better) — a weighted
blend of three "goodness" components, each normalised so that *lower rank = better = 1.0*:

    score = W_NIRF · g_nirf + W_CLOSING · g_closing + W_OPENING · g_opening

with ``W_NIRF > W_CLOSING > W_OPENING`` (see :data:`_WEIGHTS`). NIRF carries the most
weight, then closing rank, then opening rank — but because it is a *weighted sum* and not a
strict priority, a large advantage on a lower-weighted term can outweigh a small
disadvantage on a higher-weighted one. Components:

* ``g_nirf`` — from the institute's NIRF rank on a fixed scale (rank 1 → 1.0, falling off
  towards :data:`_NIRF_RANK_SCALE`); institutes absent from NIRF score 0.0.
* ``g_closing`` / ``g_opening`` — from the program's **recency-weighted** closing / opening
  ranks, min-max normalised across the result set (lowest rank → 1.0). "Recency-weighted"
  blends each year with weights that decay as years get older (``_RECENCY_DECAY`` per year),
  so *recent* closing/opening ranks dominate — surfacing currently-preferred programs over
  ones competitive only years ago.

Results are sorted by ``score`` descending (see :func:`_order_key` for the tie-break).

Each recommendation also carries, for display only (it does **not** affect ordering):

* ``feasibility`` ("Chance") — a recency-weighted admit likelihood in [0, 1] derived from
  how comfortably the candidate's rank clears each year's closing rank.
* ``in_range_years`` — the years the candidate's rank fell within that year's
  opening..closing band — and, restricted to those years, the smallest opening rank and
  largest closing rank (with their years).

This module is UI-agnostic and depends only on pandas + the local models.
"""

from __future__ import annotations

import math
from typing import Mapping

import pandas as pd

from .constants import (
    GENDER_FEMALE,
    GENDER_NEUTRAL,
    QUOTA_HOME_STATE,
)
from .models import Cutoff, Recommendation

# Steepness of the feasibility logistic on the *relative* margin (C - R) / C.
# k=6 => a closing rank 20% above the candidate's rank scores ~0.77 (comfortably safe);
# 20% below scores ~0.23 (a reach).
_FEASIBILITY_K = 6.0

# Per-year weight decay used when blending per-year values (feasibility, and the closing /
# opening ranks that drive ordering) into one recency-weighted number. A year that is `n`
# years older than the most recent contributes _RECENCY_DECAY**n of the weight, so 0.6
# means each older year counts ~60% as much as the one after it.
_RECENCY_DECAY = 0.6

# Score weights for the three ranking components, in descending priority: NIRF rank,
# closing rank, opening rank. They sum to 1 so the resulting score lands in [0, 1].
_W_NIRF = 0.6
_W_CLOSING = 0.3
_W_OPENING = 0.1
_WEIGHTS = (_W_NIRF, _W_CLOSING, _W_OPENING)

# Fixed scale for turning a NIRF rank into a goodness in [0, 1] (rank 1 -> 1.0). Roughly the
# size of the published NIRF Engineering list, so the curve spans the realistic rank range
# independently of which institutes happen to be in a given result set.
_NIRF_RANK_SCALE = 200.0

# Columns that identify one program across years.
_KEY_COLS = [
    "institute_type",
    "institute_name",
    "program_name",
    "quota",
    "seat_type",
    "gender",
]


def feasibility(rank: int, closing_rank: int | None) -> float:
    """Admit-likelihood in [0, 1] from the candidate rank and a program's closing rank.

    A missing closing rank (no seat data) is treated as unknown -> 0.0. The logistic
    exponent is clamped so extreme inputs (a tiny closing rank against a huge rank) can
    never overflow.
    """
    if closing_rank is None or pd.isna(closing_rank) or closing_rank <= 0:
        return 0.0
    relative_margin = (closing_rank - rank) / closing_rank
    x = max(-60.0, min(60.0, _FEASIBILITY_K * relative_margin))
    return 1.0 / (1.0 + math.exp(-x))


def _recency_weighted(values: list[tuple[int, float]], ref_year: int) -> float | None:
    """Blend per-year values into one number, weighting recent years more.

    ``values`` is a list of ``(year, value)``; each contributes ``_RECENCY_DECAY ** (ref_year
    - year)`` of the weight. Returns ``None`` when there are no values.
    """
    num = den = 0.0
    for year, value in values:
        w = _RECENCY_DECAY ** (ref_year - year)
        num += w * value
        den += w
    return num / den if den else None


def _nirf_goodness(nirf_rank: int | None) -> float:
    """NIRF rank -> goodness in [0, 1] (rank 1 -> 1.0). Missing rank -> 0.0 (worst)."""
    if nirf_rank is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (nirf_rank - 1) / _NIRF_RANK_SCALE))


def _lower_is_better(value: float | None, lo: float, hi: float) -> float:
    """Min-max normalise a rank-like value so the smallest (``lo``) maps to 1.0.

    Returns 0.0 for a missing value and 1.0 when the set has no spread (``hi == lo``), so a
    dimension on which every program is identical doesn't perturb the ranking.
    """
    if value is None:
        return 0.0
    if hi <= lo:
        return 1.0
    return max(0.0, min(1.0, (hi - value) / (hi - lo)))


def _assign_scores(recs: list[Recommendation]) -> None:
    """Compute and store each recommendation's weighted ``score`` in place.

    Closing/opening goodness is min-max normalised *across this result set*; NIRF goodness
    uses the fixed :data:`_NIRF_RANK_SCALE`. A program with no opening rank falls back to its
    closing goodness so the missing tertiary term never penalises it.
    """
    closings = [r.rank_closing for r in recs if r.rank_closing is not None]
    openings = [r.rank_opening for r in recs if r.rank_opening is not None]
    c_lo, c_hi = (min(closings), max(closings)) if closings else (0.0, 0.0)
    o_lo, o_hi = (min(openings), max(openings)) if openings else (0.0, 0.0)

    for r in recs:
        g_nirf = _nirf_goodness(r.nirf_rank)
        g_closing = _lower_is_better(r.rank_closing, c_lo, c_hi)
        g_opening = (
            _lower_is_better(r.rank_opening, o_lo, o_hi)
            if r.rank_opening is not None
            else g_closing
        )
        r.score = _W_NIRF * g_nirf + _W_CLOSING * g_closing + _W_OPENING * g_opening


def _order_key(rec: Recommendation) -> tuple[float, float, float, float]:
    """Sort key for final ordering: by ``score`` descending, with a deterministic tie-break
    on (NIRF rank, closing, opening) ascending. Missing values tie-break last."""
    nirf = rec.nirf_rank if rec.nirf_rank is not None else math.inf
    closing = rec.rank_closing if rec.rank_closing is not None else math.inf
    opening = rec.rank_opening if rec.rank_opening is not None else math.inf
    return (-rec.score, nirf, closing, opening)


def _closing_trend(years_rows: list[tuple[int, int, int | None, int]]) -> str | None:
    """Trend direction of the closing rank across up to 5 most recent data years.

    Uses an ordinary least-squares slope of ``(year, closing_rank)``. A positive slope
    means the cutoff rank is rising over time (program becoming **more accessible** — fewer
    candidates are picking it). A negative slope means the cutoff is falling (program
    becoming **more competitive**). Returns ``None`` when fewer than 2 data years exist.

    Threshold: ≥ 3% per year relative change is "easing" / "tighter"; below that is
    "stable". The threshold filters year-to-year noise in small data windows.
    """
    pts = [(y, c) for y, _r, _o, c in years_rows[:5]]
    if len(pts) < 2:
        return "stable"
    n = len(pts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return "stable"
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    rel = slope / y_mean  # relative change per year
    if rel > 0.03:
        return "easing"   # cutoff moving up → easier to get in
    if rel < -0.03:
        return "tighter"  # cutoff moving down → harder to get in
    return "stable"


def _gender_pool(gender: str) -> set[str]:
    """Seat-pool genders a candidate may compete in.

    Female candidates may take both gender-neutral and female-only seats; everyone else
    competes only in the gender-neutral pool.
    """
    if gender == GENDER_FEMALE:
        return {GENDER_NEUTRAL, GENDER_FEMALE}
    return {GENDER_NEUTRAL}


def _filter(
    df: pd.DataFrame,
    *,
    seat_type: str,
    gender: str,
    home_state: str | None,
    institute_types: set[str] | None,
    year: int | None,
    round: int | None,
) -> pd.DataFrame:
    out = df

    if year is not None:
        out = out[out["year"] == year]
    if round is not None:
        out = out[out["round"] == round]

    out = out[out["seat_type"] == seat_type]
    out = out[out["gender"].isin(_gender_pool(gender))]

    if institute_types:
        out = out[out["institute_type"].isin(institute_types)]

    # Home-state quota: only usable when the candidate names a home state. Without it,
    # HS seats confer no advantage, so we drop them (keep AI / OS). (Verifying the
    # institute's own state is a future refinement — see plan "Open / deferred".)
    if not home_state:
        out = out[out["quota"] != QUOTA_HOME_STATE]

    return out


def _yearly_reps(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce to one row per (program key, year): the highest round that has a closing rank.

    JoSAA publishes several rounds per year; the final round is the settled cutoff, so we
    keep the max-round row for each program/year.
    """
    d = df.dropna(subset=["closing_rank"])
    if d.empty:
        return d
    d = d.reset_index(drop=True)
    keep = d.groupby(_KEY_COLS + ["year"])["round"].idxmax()
    return d.loc[keep]


def recommend(
    rank: int,
    rank_range: int,
    *,
    seat_type: str = "OPEN",
    gender: str = GENDER_NEUTRAL,
    home_state: str | None = None,
    institute_types: set[str] | None = None,
    year: int | None = None,
    round: int | None = None,
    data: pd.DataFrame,
    nirf_by_institute: Mapping[str, tuple[int, float]] | None = None,
    limit: int | None = None,
) -> list[Recommendation]:
    """Return ranked recommendations, best first (see the module docstring for ordering).

    A program is recommended if its closing rank fell inside the rank window in *any*
    available year. Ordering is by ``(nirf_rank, recency-weighted closing, recency-weighted
    opening)`` ascending; ``feasibility`` is reported for display but does not affect order.

    Parameters
    ----------
    rank, rank_range:
        Candidate rank and the +/- window of closing ranks to consider.
    seat_type, gender, home_state, institute_types:
        Filters described in the module docstring.
    year, round:
        Optional restrictions. ``None`` (the default) considers all years/rounds so the
        cross-year summary is meaningful; pass a value to pin the analysis to one slice.
    data:
        Cutoffs DataFrame (see :data:`constants.CUTOFF_COLUMNS`).
    nirf_by_institute:
        Mapping ``institute_name -> (nirf_rank, nirf_score)`` from the latest NIRF data.
        Institutes absent from the map have no NIRF rank and sort last.
    limit:
        Optional cap on the number of results.
    """
    nirf_by_institute = nirf_by_institute or {}

    static = _filter(
        data,
        seat_type=seat_type,
        gender=gender,
        home_state=home_state,
        institute_types=institute_types,
        year=year,
        round=round,
    )
    reps = _yearly_reps(static)
    if reps.empty:
        return []

    lo, hi = rank - rank_range, rank + rank_range
    ref_year = int(reps["year"].max())

    recs: list[Recommendation] = []
    for key, grp in reps.groupby(_KEY_COLS, sort=False):
        institute_type, institute_name, program_name, quota, st, gen = (str(k) for k in key)

        # (year, round, opening, closing) per year, most recent first.
        years_rows = sorted(
            (
                (
                    int(row.year),
                    int(row.round) if not pd.isna(row.round) else 0,
                    int(row.opening_rank) if not pd.isna(row.opening_rank) else None,
                    int(row.closing_rank),
                )
                for row in grp.itertuples(index=False)
            ),
            key=lambda t: t[0],
            reverse=True,
        )

        # A year is "in range" when the candidate's rank fell within that year's
        # opening..closing band (they would have secured a seat). A missing opening rank
        # is treated as no lower bound. years_rows is already sorted recent->old, so
        # in_range_years inherits that order.
        in_range = [
            (y, o, c)
            for (y, _r, o, c) in years_rows
            if rank <= c and (o is None or o <= rank)
        ]
        in_range_years = [y for (y, _o, _c) in in_range]

        # Candidate selection uses the +/- window on closing rank, so near reaches and
        # safeties surface even in years the rank didn't land inside the band. These
        # "window years" (recent->old, inheriting years_rows' order) are what we fall back
        # to for the Open/Close display when no year was strictly in range.
        window = [(y, o, c) for (y, _r, o, c) in years_rows if lo <= c <= hi]
        if not window:
            continue
        window_years = [y for (y, _o, _c) in window]

        # Open/Close summarise a band of years: the in-range years if the rank fell inside
        # any year's opening..closing band, otherwise the window years (so a reach still
        # shows the ranks that put it near the candidate, explaining a low chance). Within
        # that band we report the smallest opening rank and the largest closing rank.
        band = in_range if in_range else window
        opens = [(y, o) for (y, o, _c) in band if o is not None]
        if opens:
            opening_min_year, opening_rank_min = min(opens, key=lambda t: t[1])
        else:
            opening_min_year, opening_rank_min = None, None
        closing_max_year, closing_rank_max = max(
            ((y, c) for (y, _o, c) in band), key=lambda t: t[1]
        )

        # Recency-weighted chance (display only) across all years with data.
        chance = _recency_weighted(
            [(y, feasibility(rank, c)) for (y, _r, _o, c) in years_rows], ref_year
        ) or 0.0

        # Recency-weighted closing / opening ranks — the ordering keys. Closing is always
        # present (years_rows is filtered to rows with a closing rank); opening may be
        # missing in some years, so we weight only the years that have it.
        rank_closing = _recency_weighted(
            [(y, float(c)) for (y, _r, _o, c) in years_rows], ref_year
        )
        rank_opening = _recency_weighted(
            [(y, float(o)) for (y, _r, o, _c) in years_rows if o is not None], ref_year
        )

        nirf = nirf_by_institute.get(institute_name)
        nirf_rank = nirf[0] if nirf else None
        nirf_score = nirf[1] if nirf else None

        trend = _closing_trend(years_rows)

        recent_year, recent_round, recent_open, recent_close = years_rows[0]
        cutoff = Cutoff(
            year=recent_year,
            round=recent_round,
            institute_type=institute_type,
            institute_name=institute_name,
            program_name=program_name,
            quota=quota,
            seat_type=st,
            gender=gen,
            opening_rank=recent_open,
            closing_rank=recent_close,
        )
        recs.append(
            Recommendation(
                cutoff=cutoff,
                nirf_rank=nirf_rank,
                nirf_score=nirf_score,
                feasibility=chance,
                in_range_years=in_range_years,
                window_years=window_years,
                opening_rank_min=opening_rank_min,
                opening_rank_min_year=opening_min_year,
                closing_rank_max=closing_rank_max,
                closing_rank_max_year=closing_max_year,
                rank_closing=rank_closing,
                rank_opening=rank_opening,
                closing_rank_trend=trend,
            )
        )

    _assign_scores(recs)
    recs.sort(key=_order_key)
    if limit is not None:
        recs = recs[:limit]
    return recs
