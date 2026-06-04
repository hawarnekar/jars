"""jars_lib — JEE (JoSAA) admission recommendation library.

Public surface for embedding apps (TUI, web, notebooks)::

    from jars_lib import recommend, load_data, RecoEngine

The engine and models carry no UI dependencies.
"""

from __future__ import annotations

from .config import Paths
from .constants import (
    GENDERS,
    GENDER_FEMALE,
    GENDER_NEUTRAL,
    IIT_TYPES,
    INSTITUTE_TYPES,
    NON_IIT_TYPES,
    SEAT_TYPES,
)
from .engine import RecoEngine, load_data
from .models import Cutoff, NirfScore, Recommendation
from .recommend import feasibility, recommend

__all__ = [
    "recommend",
    "feasibility",
    "RecoEngine",
    "load_data",
    "Cutoff",
    "NirfScore",
    "Recommendation",
    "Paths",
    "INSTITUTE_TYPES",
    "IIT_TYPES",
    "NON_IIT_TYPES",
    "SEAT_TYPES",
    "GENDERS",
    "GENDER_NEUTRAL",
    "GENDER_FEMALE",
]

__version__ = "0.1.0"
