"""Canonical vocabularies used across the JoSAA dataset and the recommendation engine.

Keeping these in one place means the scraper, storage schema, engine, and UI all agree
on spelling/casing. JoSAA's own labels are the source of truth; we normalise to these.
"""

from __future__ import annotations

# Institute families as they appear (in spirit) in the JoSAA "Institute Type" dropdown.
INSTITUTE_TYPES: tuple[str, ...] = ("IIT", "NIT", "IIIT", "GFTI")

# JoSAA uses JEE Advanced ranks for IIT allocation and JEE Mains (CRL) ranks for all
# other institutes. These sets drive the rank-type partitioning in the engine.
IIT_TYPES: frozenset[str] = frozenset({"IIT"})
NON_IIT_TYPES: frozenset[str] = frozenset({"NIT", "IIIT", "GFTI"})

# Seat types / categories. JoSAA uses these labels (PwD variants append "(PwD)").
SEAT_TYPES: tuple[str, ...] = (
    "OPEN",
    "OPEN (PwD)",
    "EWS",
    "EWS (PwD)",
    "OBC-NCL",
    "OBC-NCL (PwD)",
    "SC",
    "SC (PwD)",
    "ST",
    "ST (PwD)",
)

# Gender pools.
GENDER_NEUTRAL = "Gender-Neutral"
GENDER_FEMALE = "Female-only (including Supernumerary)"
GENDERS: tuple[str, ...] = (GENDER_NEUTRAL, GENDER_FEMALE)

# Quota labels. IITs use "AI" (All India); NIT/IIIT/GFTI use HS/OS (and a few others).
QUOTA_ALL_INDIA = "AI"
QUOTA_HOME_STATE = "HS"
QUOTA_OTHER_STATE = "OS"

# Column schema for the cutoffs table (parquet) — the canonical tidy layout.
CUTOFF_COLUMNS: tuple[str, ...] = (
    "year",
    "round",
    "institute_type",
    "institute_name",
    "program_name",
    "quota",
    "seat_type",
    "gender",
    "opening_rank",
    "closing_rank",
)
