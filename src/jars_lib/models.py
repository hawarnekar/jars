"""Plain data structures shared across the library.

These are intentionally dependency-light (stdlib dataclasses) so any consumer — TUI,
web app, notebook — can use them without pulling in pandas types at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
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
    """A scored suggestion returned by the engine.

    Wraps the underlying cutoff and adds the matched NIRF info plus the computed
    feasibility (admit likelihood, 0..1), normalised NIRF (0..1) and combined score.
    """

    cutoff: Cutoff
    nirf_rank: int | None
    nirf_score: float | None
    feasibility: float
    nirf_norm: float
    score: float

    def to_dict(self) -> dict[str, Any]:
        d = self.cutoff.to_dict()
        d.update(
            nirf_rank=self.nirf_rank,
            nirf_score=self.nirf_score,
            feasibility=round(self.feasibility, 4),
            nirf_norm=round(self.nirf_norm, 4),
            score=round(self.score, 4),
        )
        return d
