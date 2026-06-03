"""High-level facade: load the offline data once and serve recommendations.

JoSAA uses **two different rank scales**:

* **JEE Advanced rank** — for IIT seats (roughly 1.8 lakh candidates sit the exam).
* **JEE Mains rank (CRL)** — for NIT / IIIT / GFTI seats (~11 lakh candidates).

Calling ``engine.recommend()`` with both ranks returns a merged, score-sorted list
covering all institute types.  Providing only one rank restricts results to the
appropriate family automatically.

Example::

    engine = load_data()
    # IIT + non-IIT results together
    results = engine.recommend(rank_range=2000, jee_adv_rank=3000, jee_mains_rank=25000)
    # Only IIT (Advanced only)
    results = engine.recommend(rank_range=2000, jee_adv_rank=3000)
    # Only non-IIT (Mains only)
    results = engine.recommend(rank_range=5000, jee_mains_rank=25000)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .config import DEFAULT_ALPHA, Paths
from .constants import GENDER_NEUTRAL, IIT_TYPES, NON_IIT_TYPES
from .match import nirf_lookup
from .models import NirfScore, Recommendation
from .recommend import recommend as _recommend
from . import storage


@dataclass(slots=True)
class RecoEngine:
    """An in-memory view of the offline datasets plus a recommend() method."""

    cutoffs: pd.DataFrame
    nirf: list[NirfScore]
    meta: dict[str, Any] = field(default_factory=dict)
    _nirf_lookup: dict[str, tuple[int, float]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self._nirf_lookup and self.nirf is not None and len(self.cutoffs):
            names = self.cutoffs["institute_name"].dropna().astype(str).tolist()
            self._nirf_lookup = nirf_lookup(names, self.nirf)

    @property
    def is_empty(self) -> bool:
        return len(self.cutoffs) == 0

    def years(self) -> list[int]:
        return sorted({int(y) for y in self.cutoffs["year"].dropna().tolist()})

    def rounds(self, year: int) -> list[int]:
        sub = self.cutoffs[self.cutoffs["year"] == year]
        return sorted({int(r) for r in sub["round"].dropna().tolist()})

    def recommend(
        self,
        rank_range: int,
        *,
        jee_adv_rank: int | None = None,
        jee_mains_rank: int | None = None,
        seat_type: str = "OPEN",
        gender: str = GENDER_NEUTRAL,
        home_state: str | None = None,
        institute_types: set[str] | None = None,
        year: int | None = None,
        round: int | None = None,
        alpha: float = DEFAULT_ALPHA,
        limit: int | None = None,
    ) -> list[Recommendation]:
        """Return scored recommendations, best first.

        At least one of ``jee_adv_rank`` or ``jee_mains_rank`` must be supplied.

        * Only ``jee_adv_rank`` → IIT results only (Advanced rank scale).
        * Only ``jee_mains_rank`` → NIT / IIIT / GFTI results only (Mains CRL scale).
        * Both → all institute types, merged and re-sorted by score.

        The optional ``institute_types`` filter is intersected with the rank-implied
        set so you can still restrict to e.g. just NITs when providing Mains rank.
        """
        if jee_adv_rank is None and jee_mains_rank is None:
            raise ValueError("Provide at least one of jee_adv_rank or jee_mains_rank.")

        common = dict(
            seat_type=seat_type,
            gender=gender,
            home_state=home_state,
            year=year,
            round=round,
            alpha=alpha,
            data=self.cutoffs,
            nirf_by_institute=self._nirf_lookup,
        )

        recs: list[Recommendation] = []

        if jee_adv_rank is not None:
            iit_types = IIT_TYPES
            if institute_types:
                iit_types = IIT_TYPES & institute_types
            if iit_types:
                recs += _recommend(
                    jee_adv_rank, rank_range,
                    institute_types=iit_types,
                    **common,
                )

        if jee_mains_rank is not None:
            non_iit_types = NON_IIT_TYPES
            if institute_types:
                non_iit_types = NON_IIT_TYPES & institute_types
            if non_iit_types:
                recs += _recommend(
                    jee_mains_rank, rank_range,
                    institute_types=non_iit_types,
                    **common,
                )

        recs.sort(key=lambda r: r.score, reverse=True)
        if limit is not None:
            recs = recs[:limit]
        return recs


def load_data(paths: Paths | None = None) -> RecoEngine:
    """Load cutoffs + NIRF + meta from disk into a ready-to-use engine."""
    paths = paths or Paths.resolve()
    return RecoEngine(
        cutoffs=storage.load_cutoffs(paths),
        nirf=storage.load_nirf(paths),
        meta=storage.read_meta(paths),
    )
