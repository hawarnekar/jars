"""Fuzzy-map JoSAA institute names to NIRF institute names.

JoSAA writes "Indian Institute of Technology Bombay" while NIRF may list "Indian
Institute of Technology Bombay" or a slightly different form. We resolve each JoSAA name
to its best NIRF match above a similarity threshold and expose a ready-to-use lookup of
``institute_name -> (nirf_rank, nirf_score)`` for the engine. Unmatched institutes are
simply omitted (the engine then scores them on feasibility alone).
"""

from __future__ import annotations

from typing import Iterable

from rapidfuzz import fuzz, process

from .config import DEFAULT_NAME_MATCH_THRESHOLD
from .constants import shorten_institute_name
from .models import NirfScore


def _normalise(name: str) -> str:
    # Abbreviate first so long ("Indian Institute of Technology …") and short ("IIT …")
    # forms compare equal even if one side wasn't shortened at store time.
    name = shorten_institute_name(name)
    return " ".join(name.lower().replace("-", " ").replace(",", " ").split())


def build_name_map(
    josaa_names: Iterable[str],
    nirf_scores: Iterable[NirfScore],
    *,
    threshold: float = DEFAULT_NAME_MATCH_THRESHOLD,
) -> dict[str, str]:
    """Return ``{josaa_name: nirf_name}`` for matches at/above ``threshold``."""
    nirf_list = list(nirf_scores)
    nirf_norm_to_name: dict[str, str] = {}
    for s in nirf_list:
        nirf_norm_to_name.setdefault(_normalise(s.institute_name), s.institute_name)
    choices = list(nirf_norm_to_name.keys())

    mapping: dict[str, str] = {}
    for josaa_name in set(josaa_names):
        if not josaa_name:
            continue
        match = process.extractOne(
            _normalise(josaa_name), choices, scorer=fuzz.token_sort_ratio
        )
        if match and match[1] >= threshold:
            mapping[josaa_name] = nirf_norm_to_name[match[0]]
    return mapping


def nirf_lookup(
    josaa_names: Iterable[str],
    nirf_scores: Iterable[NirfScore],
    *,
    threshold: float = DEFAULT_NAME_MATCH_THRESHOLD,
) -> dict[str, tuple[int, float]]:
    """Build the engine's ``institute_name -> (nirf_rank, nirf_score)`` lookup."""
    nirf_list = list(nirf_scores)
    by_name = {s.institute_name: s for s in nirf_list}
    name_map = build_name_map(josaa_names, nirf_list, threshold=threshold)
    out: dict[str, tuple[int, float]] = {}
    for josaa_name, nirf_name in name_map.items():
        s = by_name[nirf_name]
        out[josaa_name] = (s.nirf_rank, s.nirf_score)
    return out
