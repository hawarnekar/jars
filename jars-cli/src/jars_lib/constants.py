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
# institute_state is appended at the end so tuple-based test rows (10 elements) remain valid.
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
    "institute_state",
)

# All Indian states and Union Territories, for the TUI home-state dropdown.
INDIAN_STATES: tuple[str, ...] = (
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    # Union Territories
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Lakshadweep",
    "Puducherry",
)

# Mapping from (shortened) institute name to the Indian state where it is located.
# Includes both the parquet-stored forms (post-shorten_institute_name) and the forms
# produced by shortening the fixture/full names, so lookups work in both contexts.
INSTITUTE_STATE: dict[str, str] = {
    # IITs
    "IIT Bombay": "Maharashtra",
    "IIT Delhi": "Delhi",
    "IIT Madras": "Tamil Nadu",
    "IIT Kanpur": "Uttar Pradesh",
    "IIT Kharagpur": "West Bengal",
    "IIT Roorkee": "Uttarakhand",
    "IIT Guwahati": "Assam",
    "IIT Hyderabad": "Telangana",
    "IIT (BHU) Varanasi": "Uttar Pradesh",
    "IIT (ISM) Dhanbad": "Jharkhand",
    "IIT Bhubaneswar": "Odisha",
    "IIT Gandhinagar": "Gujarat",
    "IIT Patna": "Bihar",
    "IIT Jodhpur": "Rajasthan",
    "IIT Mandi": "Himachal Pradesh",
    "IIT Indore": "Madhya Pradesh",
    "IIT Ropar": "Punjab",
    "IIT Bhilai": "Chhattisgarh",
    "IIT Dharwad": "Karnataka",
    "IIT Goa": "Goa",
    "IIT Jammu": "Jammu and Kashmir",
    "IIT Tirupati": "Andhra Pradesh",
    "IIT Palakkad": "Kerala",
    "Indian School of Mines Dhanbad": "Jharkhand",
    # NITs — parquet form (comma after "NIT,")
    "NIT, Tiruchirappalli": "Tamil Nadu",
    "NIT Karnataka, Surathkal": "Karnataka",
    "NIT, Warangal": "Telangana",
    "NIT, Andhra Pradesh": "Andhra Pradesh",
    "NIT, Jamshedpur": "Jharkhand",
    "NIT, Kurukshetra": "Haryana",
    "NIT, Manipur": "Manipur",
    "NIT, Mizoram": "Mizoram",
    "NIT, Rourkela": "Odisha",
    "NIT, Silchar": "Assam",
    "NIT, Srinagar": "Jammu and Kashmir",
    "NIT, Uttarakhand": "Uttarakhand",
    # NITs — fixture-shortening form (no comma)
    "NIT Tiruchirappalli": "Tamil Nadu",
    "NIT Warangal": "Telangana",
    "NIT Andhra Pradesh": "Andhra Pradesh",
    "NIT Jamshedpur": "Jharkhand",
    "NIT Kurukshetra": "Haryana",
    "NIT Manipur": "Manipur",
    "NIT Mizoram": "Mizoram",
    "NIT Rourkela": "Odisha",
    "NIT Silchar": "Assam",
    "NIT Srinagar": "Jammu and Kashmir",
    "NIT Uttarakhand": "Uttarakhand",
    # NITs — named forms (consistent across parquet and fixtures)
    "Malaviya NIT Jaipur": "Rajasthan",
    "Maulana Azad NIT Bhopal": "Madhya Pradesh",
    "Motilal Nehru NIT Allahabad": "Uttar Pradesh",
    "NIT Agartala": "Tripura",
    "NIT Arunachal Pradesh": "Arunachal Pradesh",
    "NIT Calicut": "Kerala",
    "NIT Delhi": "Delhi",
    "NIT Durgapur": "West Bengal",
    "NIT Goa": "Goa",
    "NIT Hamirpur": "Himachal Pradesh",
    "NIT Meghalaya": "Meghalaya",
    "NIT Nagaland": "Nagaland",
    "NIT Patna": "Bihar",
    "NIT Puducherry": "Puducherry",
    "NIT Raipur": "Chhattisgarh",
    "NIT Sikkim": "Sikkim",
    "Sardar Vallabhbhai NIT, Surat": "Gujarat",
    "Visvesvaraya NIT, Nagpur": "Maharashtra",
    "Dr. B R Ambedkar NIT, Jalandhar": "Punjab",
    # IIITs
    "IIIT, Allahabad": "Uttar Pradesh",
    "IIIT, Hyderabad": "Telangana",
    "IIIT, Design & Manufacturing, Kancheepuram": "Tamil Nadu",
    "IIIT (IIIT) Nagpur": "Maharashtra",
    "IIIT (IIIT) Pune": "Maharashtra",
    "IIIT (IIIT) Ranchi": "Jharkhand",
    "IIIT (IIIT), Sri City, Chittoor": "Andhra Pradesh",
    "IIIT (IIIT)Kota, Rajasthan": "Rajasthan",
    "IIIT Bhagalpur": "Bihar",
    "IIIT Bhopal": "Madhya Pradesh",
    "IIIT Design & Manufacturing Kurnool, Andhra Pradesh": "Andhra Pradesh",
    "IIIT Guwahati": "Assam",
    "IIIT Lucknow": "Uttar Pradesh",
    "IIIT Manipur": "Manipur",
    "IIIT SENAPATI MANIPUR": "Manipur",
    "IIIT Srirangam, Tiruchirappalli": "Tamil Nadu",
    "IIIT Surat": "Gujarat",
    "IIIT Tiruchirappalli": "Tamil Nadu",
    "IIIT(IIIT) Dharwad": "Karnataka",
    "IIIT(IIIT) Kalyani, West Bengal": "West Bengal",
    "IIIT(IIIT) Kilohrad, Sonepat, Haryana": "Haryana",
    "IIIT(IIIT) Kottayam": "Kerala",
    "IIIT(IIIT) Una, Himachal Pradesh": "Himachal Pradesh",
    "IIIT(IIIT), Sri City, Chittoor District, Andhra Pradesh": "Andhra Pradesh",
    "IIIT(IIIT), Sri City, Chittoor District, Andra Pradesh": "Andhra Pradesh",
    "IIIT(IIIT), Vadodara, Gujrat": "Gujarat",
    "IIIT, Agartala": "Tripura",
    "IIIT, Raichur, Karnataka": "Karnataka",
    "IIIT, Vadodara International Campus Diu (IIITVICD)": "Gujarat",
    "Atal Bihari Vajpayee IIIT & Management Gwalior": "Madhya Pradesh",
    "Pt. Dwarka Prasad Mishra IIIT, Design & Manufacture Jabalpur": "Madhya Pradesh",
    "International Institute of Information Technology, Bhubaneswar": "Odisha",
    "International Institute of Information Technology, Naya Raipur": "Chhattisgarh",
    # GFTIs
    "Assam University, Silchar": "Assam",
    "Birla Institute of Technology, Deoghar Off-Campus": "Jharkhand",
    "Birla Institute of Technology, Mesra, Ranchi": "Jharkhand",
    "Birla Institute of Technology, Patna Off-Campus": "Bihar",
    "CU Jharkhand": "Jharkhand",
    "Central University of Haryana": "Haryana",
    "Central University of Jammu": "Jammu and Kashmir",
    "Central University of Rajasthan, Rajasthan": "Rajasthan",
    "Central institute of Technology Kokrajar, Assam": "Assam",
    "Chhattisgarh Swami Vivekanada Technical University, Bhilai (CSVTU Bhilai)": "Chhattisgarh",
    "Gati Shakti Vishwavidyalaya, Vadodara": "Gujarat",
    "Ghani Khan Choudhary Institute of Engineering and Technology, Malda, West Bengal": "West Bengal",
    "Gurukula Kangri Vishwavidyalaya, Haridwar": "Uttarakhand",
    "HNB Garhwal University Srinagar (Garhwal)": "Uttarakhand",
    "Indian Institute of Carpet Technology, Bhadohi": "Uttar Pradesh",
    "Indian Institute of Crop Processing Technology, Thanjavur, Tamilnadu": "Tamil Nadu",
    "Indian Institute of Engineering Science and Technology, Shibpur": "West Bengal",
    "Indian Institute of Handloom Technology(IIHT), Varanasi": "Uttar Pradesh",
    "Indian Institute of Handloom Technology, Salem": "Tamil Nadu",
    "Institute of Chemical Technology, Mumbai: Indian Oil Odisha Campus, Bhubaneswar": "Odisha",
    "Institute of Engineering and Technology, Dr. H. S. Gour University. Sagar (A Central University)": "Madhya Pradesh",
    "Institute of Infrastructure, Technology, Research and Management-Ahmedabad": "Gujarat",
    "Institute of Technology, Guru Ghasidas Vishwavidyalaya (A Central University), Bilaspur, (C.G.)": "Chhattisgarh",
    "Islamic University of Science and Technology Kashmir": "Jammu and Kashmir",
    "J.K. Institute of Applied Physics & Technology, Department of Electronics & Communication, University of Allahabad- Allahabad": "Uttar Pradesh",
    "Jawaharlal Nehru University, Delhi": "Delhi",
    "Mizoram University, Aizawl": "Mizoram",
    "National Institute of Advanced Manufacturing Technology, Ranchi": "Jharkhand",
    "National Institute of Electronics and Information Technology, Ajmer (Rajasthan)": "Rajasthan",
    "National Institute of Electronics and Information Technology, Aurangabad (Maharashtra)": "Maharashtra",
    "National Institute of Electronics and Information Technology, Gorakhpur (UP)": "Uttar Pradesh",
    "National Institute of Electronics and Information Technology, Patna (Bihar)": "Bihar",
    "National Institute of Electronics and Information Technology, Ropar (Punjab)": "Punjab",
    "National Institute of Food Technology Entrepreneurship and Management, Kundli": "Haryana",
    "National Institute of Food Technology Entrepreneurship and Management, Sonepat, Haryana": "Haryana",
    "National Institute of Food Technology Entrepreneurship and Management, Thanjavur": "Tamil Nadu",
    "National Institute of Food Technology, Entrepreneurship and Management (NIFTEM) - Thanjavur": "Tamil Nadu",
    "National Institute of Foundry & Forge Technology, Hatia, Ranchi": "Jharkhand",
    "North Eastern Regional Institute of Science and Technology, Nirjuli-791109 (Itanagar),Arunachal Pradesh": "Arunachal Pradesh",
    "North-Eastern Hill University, Shillong": "Meghalaya",
    "Pondicherry Engineering College, Puducherry": "Puducherry",
    "Puducherry Technological University, Puducherry": "Puducherry",
    "Punjab Engineering College, Chandigarh": "Chandigarh",
    "Rajiv Gandhi National Aviation University, Fursatganj, Amethi (UP)": "Uttar Pradesh",
    "Sant Longowal Institute of Engineering and Technology": "Punjab",
    "School of Engineering, Tezpur University, Napaam, Tezpur": "Assam",
    "School of Planning & Architecture, Bhopal": "Madhya Pradesh",
    "School of Planning & Architecture, New Delhi": "Delhi",
    "School of Planning & Architecture: Vijayawada": "Andhra Pradesh",
    "School of Studies of Engineering and Technology, Guru Ghasidas Vishwavidyalaya, Bilaspur": "Chhattisgarh",
    "Shri G. S. Institute of Technology and Science Indore": "Madhya Pradesh",
    "Shri Mata Vaishno Devi University, Katra, Jammu & Kashmir": "Jammu and Kashmir",
    "University of Hyderabad": "Telangana",
    "lndian Institute of Food Processing Technology, Thanjavur, Tamil Naidu.": "Tamil Nadu",
}

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
