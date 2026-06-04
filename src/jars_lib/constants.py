"""Canonical vocabularies used across the JoSAA dataset and the recommendation engine.

Keeping these in one place means the scraper, storage schema, engine, and UI all agree
on spelling/casing. JoSAA's own labels are the source of truth; we normalise to these.
"""

from __future__ import annotations

import re

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

# Long institute prefixes abbreviated when names are stored. Ordered longest-first so
# "Indian Institute of Information Technology" is matched before the shorter "Indian
# Institute of Technology" prefix (they don't actually overlap as substrings, but this
# keeps the intent explicit and order-safe).
INSTITUTE_NAME_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    ("Indian Institute of Information Technology", "IIIT"),
    ("Indian Institute of Technology", "IIT"),
    ("National Institute of Technology", "NIT"),
)

_ABBREV_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(re.escape(long), re.IGNORECASE), short)
    for long, short in INSTITUTE_NAME_ABBREVIATIONS
)


def shorten_institute_name(name: str) -> str:
    """Abbreviate long IIT/NIT/IIIT prefixes in a fetched institute name.

    e.g. "Indian Institute of Technology Bombay" -> "IIT Bombay",
    "Malaviya National Institute of Technology Jaipur" -> "Malaviya NIT Jaipur".
    Idempotent: applying it to an already-shortened name is a no-op.
    """
    if not name:
        return name
    out = name
    for pattern, short in _ABBREV_PATTERNS:
        out = pattern.sub(short, out)
    return re.sub(r"\s+", " ", out).strip()


# Long degree descriptors abbreviated when program names are stored. Order matters: the
# compound phrases must precede the shorter "Bachelor of …" / "Master of Science" rules,
# which would otherwise match inside them and block the compound replacement.
PROGRAM_NAME_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    ("Bachelor of Science and Master of Science (Dual Degree)", "B.S. + M.S."),
    ("Bachelor and Master of Technology (Dual Degree)", "B.Tech. + M.Tech."),
    ("Bachelor of Science and MBA (Dual Degree)", "B.S. and MBA"),
    ("Bachelor of Technology and MBA (Dual Degree)", "B.Tech. and MBA"),
    ("B.Tech. + M.Tech./MS (Dual Degree)", "B.Tech. + M.Tech./M.S."),
    ("Integrated Bachelor of Science-Master of Science", "B.S. + M.S."),
    ("Integrated Master of Technology", "B.Tech. + M.Tech."),
    ("Bachelor of Technology", "B.Tech."),
    ("Bachelor of Science", "B.S."),
    ("Master of Science", "M.S."),
)

_PROGRAM_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(re.escape(long), re.IGNORECASE), short)
    for long, short in PROGRAM_NAME_ABBREVIATIONS
)


def shorten_program_name(name: str) -> str:
    """Abbreviate long degree descriptors in a fetched program name.

    e.g. "Computer Science and Engineering (4 Years, Bachelor of Technology)" ->
    "Computer Science and Engineering (4 Years, B.Tech.)"; the dual-degree /
    integrated-masters phrases collapse to "Dual Degree". Idempotent.
    """
    if not name:
        return name
    out = name
    for pattern, short in _PROGRAM_PATTERNS:
        out = pattern.sub(short, out)
    return re.sub(r"\s+", " ", out).strip()
