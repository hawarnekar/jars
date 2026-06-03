"""The recommendation engine — the core reusable API.

Given a candidate's rank and a +/- window, plus their category/gender/state and an
institute-type filter, it returns scored program suggestions. The score blends:

    score = alpha * feasibility + (1 - alpha) * nirf_norm

where ``feasibility`` is the admit-likelihood implied by last year's closing rank and
``nirf_norm`` is the institute's normalised NIRF Engineering score. ``alpha`` lets the
user tilt between "safest admit" (alpha->1) and "best-ranked college" (alpha->0).

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

# NIRF scores are published on a 0..100 scale.
_NIRF_SCALE = 100.0


def feasibility(rank: int, closing_rank: int | None) -> float:
    """Admit-likelihood in [0, 1] from the candidate rank and a program's closing rank.

    A missing closing rank (no seat data) is treated as unknown -> 0.0.
    """
    if closing_rank is None or pd.isna(closing_rank) or closing_rank <= 0:
        return 0.0
    relative_margin = (closing_rank - rank) / closing_rank
    return 1.0 / (1.0 + math.exp(-_FEASIBILITY_K * relative_margin))


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


def _latest(df: pd.DataFrame, col: str) -> int | None:
    vals = df[col].dropna()
    return int(vals.max()) if len(vals) else None


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
    alpha: float = 0.5,
    data: pd.DataFrame,
    nirf_by_institute: Mapping[str, tuple[int, float]] | None = None,
    limit: int | None = None,
) -> list[Recommendation]:
    """Return scored recommendations, best first.

    Parameters
    ----------
    rank, rank_range:
        Candidate rank and the +/- window of closing ranks to consider.
    seat_type, gender, home_state, institute_types:
        Filters described in the module docstring.
    year, round:
        Defaults to the latest available year and its highest round.
    alpha:
        Weight on feasibility vs NIRF, in [0, 1].
    data:
        Cutoffs DataFrame (see :data:`constants.CUTOFF_COLUMNS`).
    nirf_by_institute:
        Mapping ``institute_name -> (nirf_rank, nirf_score)``. Institutes absent from the
        map get nirf_norm = 0.0 (feasibility-only scoring still applies).
    limit:
        Optional cap on the number of results.
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1]")
    nirf_by_institute = nirf_by_institute or {}

    if year is None:
        year = _latest(data, "year")
    if round is None and year is not None:
        round = _latest(data[data["year"] == year], "round")

    filtered = _filter(
        data,
        seat_type=seat_type,
        gender=gender,
        home_state=home_state,
        institute_types=institute_types,
        year=year,
        round=round,
    )

    lo, hi = rank - rank_range, rank + rank_range
    closing = filtered["closing_rank"]
    windowed = filtered[closing.notna() & (closing >= lo) & (closing <= hi)]

    recs: list[Recommendation] = []
    for row in windowed.itertuples(index=False):
        c_rank = int(row.closing_rank) if not pd.isna(row.closing_rank) else None
        o_rank = int(row.opening_rank) if not pd.isna(row.opening_rank) else None
        cutoff = Cutoff(
            year=int(row.year),
            round=int(row.round),
            institute_type=str(row.institute_type),
            institute_name=str(row.institute_name),
            program_name=str(row.program_name),
            quota=str(row.quota),
            seat_type=str(row.seat_type),
            gender=str(row.gender),
            opening_rank=o_rank,
            closing_rank=c_rank,
        )
        nirf = nirf_by_institute.get(cutoff.institute_name)
        nirf_rank = nirf[0] if nirf else None
        nirf_score = nirf[1] if nirf else None
        nirf_norm = (nirf_score / _NIRF_SCALE) if nirf_score is not None else 0.0
        nirf_norm = max(0.0, min(1.0, nirf_norm))

        feas = feasibility(rank, c_rank)
        score = alpha * feas + (1.0 - alpha) * nirf_norm
        recs.append(
            Recommendation(
                cutoff=cutoff,
                nirf_rank=nirf_rank,
                nirf_score=nirf_score,
                feasibility=feas,
                nirf_norm=nirf_norm,
                score=score,
            )
        )

    recs.sort(key=lambda r: r.score, reverse=True)
    if limit is not None:
        recs = recs[:limit]
    return recs
