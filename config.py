"""
config.py - Production Configuration
Dynamic client profile + US-focused recruiter outreach
"""

import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# DIRECTORIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

OUTPUT_DIR = BASE_DIR / "outputs"
RESUME_DIR = BASE_DIR / "resumes"
TEMPLATES_DIR = BASE_DIR / "templates"
CREDENTIALS_DIR = BASE_DIR / "credentials"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"

for directory in [
    OUTPUT_DIR,
    RESUME_DIR,
    TEMPLATES_DIR,
    CREDENTIALS_DIR,
    SCREENSHOTS_DIR,
]:
    directory.mkdir(exist_ok=True)


# ============================================================
# FILES
# ============================================================

LEADS_CSV = OUTPUT_DIR / "leads.csv"
SENT_LOG_CSV = OUTPUT_DIR / "sent_log.csv"
CANDIDATE_DATA_FILE = BASE_DIR / "candidate_data.json"

GMAIL_CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
GMAIL_TOKEN_FILE = CREDENTIALS_DIR / "token.json"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose"
]


# ============================================================
# SENDER
# ============================================================

SENDER_EMAIL = os.getenv(
    "SENDER_EMAIL",
    "rahuljha1229@gmail.com"
)

SENDER_NAME = os.getenv(
    "SENDER_NAME",
    "Alok Jha"
)


# ============================================================
# VALUE CLEANING
# ============================================================

def _clean_value(value, default=""):
    value = str(value or "").strip()

    invalid = {
        "",
        "none",
        "nan",
        "n/a",
        "na",
        "null",
        "not mentioned",
        "not available",
        "unknown",
    }

    if value.lower() in invalid:
        return default

    return value


# ============================================================
# CANDIDATE DATA
# ============================================================

def load_candidate_data() -> dict:

    fallback = {
        "full_name": "Siddhu Kolamala",
        "name": "Siddhu Kolamala",
        "title": "Digital Marketing Specialist",

        "email": "supaysid@gmail.com",
        "phone": "+1 973-687-9494",

        "linkedin": "https://linkedin.com/in/kolamala-siddhu",

        "experience": "",
        "total_experience": "",

        "availability": "Immediate",

        "location": "New York, NY",
        "current_location": "New York, NY",

        "preferred_location": "Remote / Hybrid / Onsite",

        "open_to_relocate": "Yes",

        "work_authorization": "",

        # IMPORTANT:
        # This is the BCC tracking address.
        "employer_email": "kim@jpitstaffing.com",

        "employer_phone": "+1 571-626-5445",

        # Optional custom search keywords.
        "search_keywords": [],
    }

    if not CANDIDATE_DATA_FILE.exists():
        return fallback

    try:
        with open(
            CANDIDATE_DATA_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            fallback.update(data)

        return fallback

    except Exception as exc:

        print(
            f"⚠️ Could not load candidate_data.json: {exc}"
        )

        return fallback


CURRENT_CANDIDATE = load_candidate_data()


# ============================================================
# EMAIL ROUTING
# ============================================================

TRACKING_EMAIL = _clean_value(
    CURRENT_CANDIDATE.get("employer_email"),
    os.getenv("TRACKING_EMAIL", "")
)

CLIENT_CC_EMAIL = _clean_value(
    CURRENT_CANDIDATE.get("email"),
    ""
)


# ============================================================
# LINKEDIN
# ============================================================

LINKEDIN_BASE_URL = (
    "https://www.linkedin.com"
)

LINKEDIN_SEARCH_URL = (
    "https://www.linkedin.com/search/results/content/"
)


# ============================================================
# STRICT US SEARCH SETTINGS
# ============================================================

US_ONLY = True

US_COUNTRY_TERMS = [
    "united states",
    "united states of america",
    "usa",
    "u.s.",
    "u.s.a",
    "us",
]

US_STATE_TERMS = [
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
    "district of columbia",
]

US_STATE_ABBREVIATIONS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE",
    "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
    "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
    "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC"
]

NON_US_COUNTRY_TERMS = [
    "india",
    "indian",
    "canada",
    "uk",
    "united kingdom",
    "australia",
    "new zealand",
    "singapore",
    "malaysia",
    "philippines",
    "pakistan",
    "bangladesh",
    "nepal",
    "uae",
    "dubai",
    "saudi arabia",
    "qatar",
    "kuwait",
    "germany",
    "france",
    "netherlands",
    "ireland",
    "europe",
    "south africa",
]


def is_probably_us_location(location: str) -> bool:

    text = str(location or "").strip().lower()

    if not text:
        return False

    # Explicit non-US country gets rejected.
    for country in NON_US_COUNTRY_TERMS:

        if re.search(
            rf"\b{re.escape(country)}\b",
            text
        ):
            return False

    # Explicit US country.
    for country in US_COUNTRY_TERMS:

        if country in text:
            return True

    # US state names.
    for state in US_STATE_TERMS:

        if re.search(
            rf"\b{re.escape(state)}\b",
            text
        ):
            return True

    # State abbreviation such as NY, CA, TX.
    for abbreviation in US_STATE_ABBREVIATIONS:

        if re.search(
            rf"(?:,\s*|\s+){re.escape(abbreviation.lower())}(?:\s|,|$)",
            text
        ):
            return True

    return False


# ============================================================
# SEARCH KEYWORDS
# ============================================================

def get_default_search_keywords() -> list:

    custom = CURRENT_CANDIDATE.get(
        "search_keywords"
    )

    if isinstance(custom, list) and custom:

        return [
            str(keyword).strip()
            for keyword in custom
            if str(keyword).strip()
        ]

    title = _clean_value(
        CURRENT_CANDIDATE.get("title"),
        "Digital Marketing Specialist"
    )

    title_low = title.lower()

    # --------------------------------------------------------
    # DIGITAL MARKETING / SEO
    # --------------------------------------------------------

    if any(
        keyword in title_low
        for keyword in [
            "digital marketing",
            "seo",
            "ppc",
            "marketing",
        ]
    ):

        return [
            "SEO Specialist hiring",
            "SEO Executive hiring",
            "SEO Analyst hiring",
            "Technical SEO Specialist hiring",

            "Digital Marketing Specialist hiring",
            "Digital Marketing Executive hiring",
            "Digital Marketing Manager hiring",

            "PPC Specialist hiring",
            "Google Ads Specialist hiring",
            "SEM Specialist hiring",

            "Performance Marketing Specialist hiring",
            "Performance Marketing Executive hiring",

            "Paid Media Specialist hiring",

            "Growth Marketing Specialist hiring",
            "Growth Marketing Executive hiring",

            "Content Marketing Specialist hiring",

            "Email Marketing Specialist hiring",
            "Marketing Automation Specialist hiring",

            "Lead Generation Specialist hiring",
            "Demand Generation Specialist hiring",

            "Social Media Specialist hiring",

            "Marketing Analyst hiring",
            "Marketing Operations Specialist hiring",
        ]

    # --------------------------------------------------------
    # GENERIC CLIENT
    # --------------------------------------------------------

    return [
        f"Hiring {title}",
        f"{title} hiring",
        f"{title} requirement",
        f"{title} opening",
        f"{title} recruiter",
        f"{title} opportunity",
    ]


DEFAULT_SEARCH_KEYWORDS = (
    get_default_search_keywords()
)


# ============================================================
# BAD LEAD KEYWORDS
# ============================================================

BAD_LEAD_KEYWORDS = [

    "bench sales",
    "bench-sales",

    "hotlist",
    "hot list",

    "consultant available",
    "available consultant",

    "available candidates",
    "candidate available",

    "available consultants",

    "vendor list",

    "marketing bench",
    "bench candidate",
    "bench recruiter",
    "bench marketing",

    "c2c candidates available",
    "looking for c2c candidates",

    "requirements & hotlist",
    "requirements and hotlist",

    "hotlist sharing",

    "training and placement",
    "placement support",
    "job support",

    "proxy interview",
    "fake profile",

    "pay after placement",

    "staffing vendor",

    "consultants available",
]


# ============================================================
# GOOD LEAD KEYWORDS
# ============================================================

GOOD_LEAD_KEYWORDS = [

    "hiring",
    "we're hiring",
    "we are hiring",

    "need",
    "requirement",
    "requirements",

    "opening",
    "open position",
    "position",

    "looking for",
    "seeking",

    "opportunity",

    "send resume",
    "share resume",
    "email resume",
    "submit resume",

    "interested candidates",

    "remote",
    "hybrid",
    "onsite",

    "contract",
    "full time",
    "part time",

    # Marketing
    "seo",
    "seo specialist",
    "seo executive",
    "seo analyst",

    "digital marketing",
    "digital marketing specialist",
    "digital marketing executive",

    "ppc",
    "google ads",
    "paid search",
    "sem",

    "performance marketing",
    "paid media",

    "growth marketing",

    "content marketing",

    "email marketing",
    "marketing automation",

    "lead generation",
    "demand generation",

    "social media",

    "conversion rate optimization",

    "keyword research",
    "competitor analysis",

    "landing page optimization",

    "campaign management",

    "mailchimp",
    "hubspot",

    "google analytics",

    "facebook ads",
    "linkedin ads",
]


# ============================================================
# PERFORMANCE
# ============================================================

MIN_ACTION_DELAY = 0.15
MAX_ACTION_DELAY = 0.35

MAX_POSTS_PER_KEYWORD = 75
MAX_SCROLL_ATTEMPTS = 6

PAGE_LOAD_TIMEOUT = 25

EMAIL_SEND_DELAY = 7

MAX_EMAILS_PER_SESSION = 100


# ============================================================
# SAFETY
# ============================================================

DRY_RUN = (
    os.getenv(
        "DRY_RUN",
        "true"
    ).lower()
    == "true"
)


# ============================================================
# RESUME
# ============================================================

def _safe_filename(text: str) -> str:

    text = str(text or "").strip()

    text = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        text
    )

    text = re.sub(
        r"_+",
        "_",
        text
    ).strip("_")

    return text or "Candidate"


_candidate_safe_name = _safe_filename(
    CURRENT_CANDIDATE.get("full_name")
    or CURRENT_CANDIDATE.get("name")
    or "Candidate"
)


DEFAULT_RESUME_FILENAME = os.getenv(
    "DEFAULT_RESUME_FILENAME",
    f"{_candidate_safe_name}_Resume.pdf"
)

DEFAULT_RESUME_PATH = (
    RESUME_DIR / DEFAULT_RESUME_FILENAME
)


# ============================================================
# CHROME
# ============================================================

CHROME_PROFILE_DIR = os.getenv(
    "CHROME_PROFILE_DIR",
    ""
)

HEADLESS_MODE = False