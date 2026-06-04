"""Plain data structures shared across the library.

These are intentionally dependency-light (stdlib dataclasses) so any consumer — TUI,
web app, notebook — can use them without pulling in pandas types at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass(slots=True)
class Cutoff:
    """One opening/closing-rank row from the JoSAA archive."""

    year: int
    round: int
    institute_type: str
    institute_name: str
    program_name: str
    quota: str
    seat_type: str
    gender: str
    opening_rank: int | None
    closing_rank: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NirfScore:
    """One NIRF Engineering ranking entry."""

    year: int
    institute_name: str
    nirf_rank: int
    nirf_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Recommendation:
    """A ranked suggestion returned by the engine.

    A recommendation summarises one program (institute + program + category + quota +
    gender) across *all* available years, not a single year:

    * ``feasibility`` is the recency-weighted admit likelihood (0..1) — recent years
      where the candidate's rank fell in range count more than older ones. It is shown
      to users as "Chance" but does **not** affect ordering.
    * ``in_range_years`` lists the years (recent→old) the candidate's rank fell within
      that year's opening..closing band — i.e. years they would have secured a seat. It is
      empty for a "reach" the rank never cleared.
    * ``window_years`` lists the years (recent→old) the program's closing rank fell within
      the candidate's ±range window — the selection years. Always non-empty.
    * ``opening_rank_min`` / ``closing_rank_max`` summarise a band of years — the best
      (smallest) opening rank and the worst (largest) closing rank, each with its year.
      The band is the in-range years when there are any, otherwise the window years (so a
      reach still shows the nearby ranks that explain its low chance).
    * ``nirf_*`` come from the latest NIRF Engineering dataset.
    * ``rank_closing`` / ``rank_opening`` are the recency-weighted closing/opening ranks
      across all of the program's years (recent years weighted more).
    * ``score`` is the weighted ranking score in [0, 1] (higher is better): a blend of NIRF
      rank, ``rank_closing``, and ``rank_opening`` goodness, weighted in that priority.
      Results are sorted by it. See :func:`jars_lib.recommend.recommend`.

    ``cutoff`` carries the most-recent year's row for identity/back-reference.
    """

    cutoff: Cutoff
    nirf_rank: int | None
    nirf_score: float | None
    feasibility: float
    in_range_years: list[int] = field(default_factory=list)
    window_years: list[int] = field(default_factory=list)
    opening_rank_min: int | None = None
    opening_rank_min_year: int | None = None
    closing_rank_max: int | None = None
    closing_rank_max_year: int | None = None
    rank_closing: float | None = None
    rank_opening: float | None = None
    score: float = 0.0
    closing_rank_trend: str | None = None

    @property
    def band_in_range(self) -> bool:
        """Whether Open/Close/`band_years` reflect in-range years (True) or the
        near-window reach fallback (False)."""
        return bool(self.in_range_years)

    @property
    def band_years(self) -> list[int]:
        """The years summarised by ``opening_rank_min`` / ``closing_rank_max``: the
        in-range years when present, otherwise the window (reach) years."""
        return self.in_range_years or self.window_years

    def to_dict(self) -> dict[str, Any]:
        d = self.cutoff.to_dict()
        d.update(
            nirf_rank=self.nirf_rank,
            nirf_score=self.nirf_score,
            feasibility=round(self.feasibility, 4),
            chance=round(self.feasibility, 4),
            score=round(self.score, 4),
            in_range_years=list(self.in_range_years),
            window_years=list(self.window_years),
            band_in_range=self.band_in_range,
            opening_rank_min=self.opening_rank_min,
            opening_rank_min_year=self.opening_rank_min_year,
            closing_rank_max=self.closing_rank_max,
            closing_rank_max_year=self.closing_rank_max_year,
            rank_closing=round(self.rank_closing, 1) if self.rank_closing is not None else None,
            rank_opening=round(self.rank_opening, 1) if self.rank_opening is not None else None,
            closing_rank_trend=self.closing_rank_trend,
        )
        return d
