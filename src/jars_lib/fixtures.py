"""A tiny hand-made dataset so the engine, CLI, and TUI work before any scrape.

Numbers are illustrative (loosely realistic) — not authoritative cutoffs. Use the
``update`` flow to populate the real offline database.
"""

from __future__ import annotations

import pandas as pd

from .constants import (
    CUTOFF_COLUMNS,
    GENDER_FEMALE,
    GENDER_NEUTRAL,
    QUOTA_ALL_INDIA,
    QUOTA_HOME_STATE,
    QUOTA_OTHER_STATE,
)
from .models import NirfScore

_YEAR = 2025
_ROUND = 6

# (institute_type, institute_name, program, quota, seat_type, gender, open, close)
_ROWS = [
    ("IIT", "Indian Institute of Technology Bombay", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_NEUTRAL, 1, 67),
    ("IIT", "Indian Institute of Technology Bombay", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_FEMALE, 12, 290),
    ("IIT", "Indian Institute of Technology Delhi", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_NEUTRAL, 68, 120),
    ("IIT", "Indian Institute of Technology Delhi", "Mathematics and Computing (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_NEUTRAL, 150, 380),
    ("IIT", "Indian Institute of Technology Madras", "Electrical Engineering (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_NEUTRAL, 700, 1600),
    ("IIT", "Indian Institute of Technology Madras", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_NEUTRAL, 130, 220),
    ("IIT", "Indian Institute of Technology Kanpur", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_NEUTRAL, 180, 260),
    ("IIT", "Indian Institute of Technology Hyderabad", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_NEUTRAL, 400, 700),
    ("IIT", "Indian Institute of Technology Hyderabad", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OBC-NCL", GENDER_NEUTRAL, 120, 320),
    ("NIT", "National Institute of Technology Tiruchirappalli", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_OTHER_STATE, "OPEN", GENDER_NEUTRAL, 900, 2100),
    ("NIT", "National Institute of Technology Tiruchirappalli", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_HOME_STATE, "OPEN", GENDER_NEUTRAL, 1500, 4200),
    ("NIT", "National Institute of Technology Karnataka, Surathkal", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_OTHER_STATE, "OPEN", GENDER_NEUTRAL, 1100, 2500),
    ("NIT", "National Institute of Technology Warangal", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_OTHER_STATE, "OPEN", GENDER_NEUTRAL, 1400, 3000),
    ("NIT", "Malaviya National Institute of Technology Jaipur", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_HOME_STATE, "OPEN", GENDER_NEUTRAL, 4000, 9000),
    ("IIIT", "Indian Institute of Information Technology, Hyderabad", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_NEUTRAL, 2000, 3500),
    ("IIIT", "Indian Institute of Information Technology, Allahabad", "Information Technology (4 Years, Bachelor of Technology)", QUOTA_ALL_INDIA, "OPEN", GENDER_NEUTRAL, 4500, 7800),
    ("GFTI", "Indian Institute of Engineering Science and Technology, Shibpur", "Computer Science and Engineering (4 Years, Bachelor of Technology)", QUOTA_OTHER_STATE, "OPEN", GENDER_NEUTRAL, 5000, 9500),
]

_NIRF = [
    NirfScore(_YEAR, "Indian Institute of Technology Madras", 1, 89.46),
    NirfScore(_YEAR, "Indian Institute of Technology Delhi", 2, 86.66),
    NirfScore(_YEAR, "Indian Institute of Technology Bombay", 3, 83.09),
    NirfScore(_YEAR, "Indian Institute of Technology Kanpur", 4, 82.79),
    NirfScore(_YEAR, "Indian Institute of Technology Kharagpur", 5, 76.88),
    NirfScore(_YEAR, "National Institute of Technology Tiruchirappalli", 9, 71.0),
    NirfScore(_YEAR, "Indian Institute of Technology Hyderabad", 8, 71.55),
    NirfScore(_YEAR, "National Institute of Technology Karnataka Surathkal", 17, 66.04),
    NirfScore(_YEAR, "National Institute of Technology Warangal", 21, 63.6),
    NirfScore(_YEAR, "Indian Institute of Information Technology Allahabad", 84, 52.0),
    NirfScore(_YEAR, "Malaviya National Institute of Technology Jaipur", 37, 58.92),
    NirfScore(_YEAR, "Indian Institute of Engineering Science and Technology Shibpur", 56, 55.4),
]


def cutoffs_df() -> pd.DataFrame:
    rows = []
    for it, inst, prog, quota, seat, gender, open_r, close_r in _ROWS:
        rows.append(
            dict(
                year=_YEAR,
                round=_ROUND,
                institute_type=it,
                institute_name=inst,
                program_name=prog,
                quota=quota,
                seat_type=seat,
                gender=gender,
                opening_rank=open_r,
                closing_rank=close_r,
            )
        )
    return pd.DataFrame(rows, columns=list(CUTOFF_COLUMNS))


def nirf_scores() -> list[NirfScore]:
    return list(_NIRF)
