"""
linkedin_scraper.py - LinkedIn Post Scraper Module

STRICT USA-ONLY VERSION

Purpose:
- Scrape LinkedIn posts for recruiter/job leads.
- Accept ONLY posts with explicit US location signals.
- Reject foreign, mixed-country, global and ambiguous posts.
- Apply strict recruiter email validation.
- Avoid bounce-risk and obviously fake emails.
"""

import time
import random
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    WebDriverException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import (
    MIN_ACTION_DELAY,
    MAX_ACTION_DELAY,
    MAX_POSTS_PER_KEYWORD,
    MAX_SCROLL_ATTEMPTS,
    CHROME_PROFILE_DIR,
    HEADLESS_MODE,
    SCREENSHOTS_DIR,
)

from src.email_extractor import extract_emails


logger = logging.getLogger(__name__)

EFFECTIVE_MAX_POSTS_PER_KEYWORD = 50


# ============================================================
# FAST MODE
# ============================================================

FAST_PAGE_BLOCK_LIMIT = 500
FAST_SCROLL_ATTEMPTS = 8
DEEP_SCAN_POST_LIMIT = 20
SAVE_SEARCH_SCREENSHOTS = False

SKIP_DEEP_SCAN_WHEN_FAST_LEADS_FOUND = True


# ============================================================
# BLOCKED / SPAM TERMS
# ============================================================

BLOCKED_TERMS = [
    "training and placement",
    "placement support",
    "job support",
    "proxy interview",
    "fake profile",
    "pay after placement",
    "100% placement",
    "consultancy fees",
    "course fee",
    "paid training",
    "we provide professional marketing",
    "bench sales",
    "hotlist",
    "hot list",
    "vendor list",
    "available candidates",
    "available consultants",
    "share hotlist",
    "requirements & hotlist",
    "requirements and hotlist",
    "hire-bangladesh",
    "hire-india",
    "hire-pakistan",
]


PAGE_DUMP_TERMS = [
    "skip to search",
    "skip to main content",
    "try premium",
    "linkedin news",
    "messaging",
    "notifications",
    "my network",
    "for business",
    "are these results helpful",
    "your feedback helps us improve",
    "linkedin corporation",
    "privacy & terms",
]


# ============================================================
# MARKETING
# ============================================================

MARKETING_TERMS = [
    "seo",
    "seo specialist",
    "seo executive",
    "seo analyst",
    "digital marketing",
    "digital marketer",
    "marketing specialist",
    "marketing executive",
    "marketing coordinator",
    "ppc",
    "google ads",
    "paid search",
    "sem",
    "performance marketing",
    "growth marketing",
    "content marketing",
    "email marketing",
    "marketing automation",
    "social media",
    "lead generation",
    "demand generation",
]


# ============================================================
# SOFTWARE / IT INTERNSHIP
# ============================================================

SOFTWARE_INTERNSHIP_TERMS = [
    "software engineer intern",
    "software engineering intern",
    "software engineering internship",
    "software developer intern",
    "software developer internship",
    "sde intern",
    "developer intern",
    "development intern",
    "programmer intern",
    "backend developer intern",
    "backend engineer intern",
    "backend internship",
    "java developer intern",
    "java engineer intern",
    "java internship",
    "python developer intern",
    "python engineer intern",
    "python internship",
    "full stack developer intern",
    "full stack engineer intern",
    "full stack intern",
    "frontend developer intern",
    "front end developer intern",
    "frontend intern",
    "web developer intern",
    "web development internship",
    "application developer intern",
    "mobile developer intern",
    "android developer intern",
    "ios developer intern",
    "computer science intern",
    "computer science internship",
    "technology intern",
    "information technology intern",
    "it intern",
    "technical intern",
    "data analyst intern",
    "data analytics intern",
    "data science intern",
    "business intelligence intern",
    "power bi intern",
    "software qa intern",
    "qa intern",
    "quality assurance intern",
    "test engineer intern",
    "cloud intern",
    "devops intern",
    "automation intern",
    "systems intern",
    "software co-op",
    "software engineering co-op",
    "developer co-op",
    "summer software intern",
    "fall software intern",
    "spring software intern",
]


IRRELEVANT_INTERNSHIP_TERMS = [
    "structural design intern",
    "civil engineering intern",
    "mechanical engineering intern",
    "electrical engineering intern",
    "behavioral technician",
    "food and beverage",
    "collections representative",
    "sales representative",
    "marketing intern",
    "human resources intern",
    "hr intern",
    "finance intern",
    "accounting intern",
    "nursing intern",
    "pharmacy intern",
    "construction intern",
    "architecture intern",
]


# ============================================================
# EMAIL QUALITY FILTERS
# ============================================================

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "aol.com",
    "protonmail.com",
    "live.com",
    "msn.com",
}


BLOCKED_EMAIL_DOMAINS = {
    "example.com",
    "test.com",
    "domain.com",
    "company.com",
    "email.com",
    "linkedin.com",
    "mail.com",
    "gmai.com",
    "gmial.com",
    "gmail.co",
    "gmail.con",
    "outlook.con",
    "yahoo.con",
}


BLOCKED_EMAIL_LOCAL_PARTS = {
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "support",
    "help",
    "info",
    "admin",
    "webmaster",
    "privacy",
    "legal",
    "sales",
    "marketing",
    "newsletter",
}


EMAIL_REGEX_STRICT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._%+\-]{0,63}"
    r"@"
    r"[A-Za-z0-9][A-Za-z0-9.\-]{1,253}"
    r"\.[A-Za-z]{2,24}$"
)


COMMON_BAD_TLDS = {
    "con",
    "comm",
    "cpm",
    "vom",
    "cim",
    "om",
    "cm",
    "coom",
    "come",
}


VALID_TLDS = {
    "com",
    "net",
    "org",
    "io",
    "co",
    "ai",
    "us",
    "ca",
    "in",
    "uk",
    "edu",
    "gov",
    "mil",
    "biz",
    "info",
    "me",
    "tv",
    "live",
    "studio",
    "tech",
    "dev",
    "app",
    "cloud",
    "consulting",
    "solutions",
    "services",
    "global",
    "staffing",
    "agency",
    "careers",
    "jobs",
    "inc",
    "llc",
    "group",
    "team",
    "company",
    "digital",
    "marketing",
    "media",
    "my",
    "sg",
    "ae",
    "au",
    "nz",
    "ie",
    "de",
    "fr",
    "nl",
    "se",
    "ch",
    "jp",
    "ph",
    "id",
    "za",
    "pk",
    "bd",
    "lk",
    "np",
    "qa",
    "sa",
    "kw",
    "om",
    "mx",
    "br",
    "es",
    "it",
    "pl",
    "ro",
    "pt",
    "be",
    "at",
    "dk",
    "no",
    "fi",
    "cz",
    "gr",
    "tr",
    "il",
    "xyz",
    "online",
    "site",
    "work",
    "world",
    "pro",
    "expert",
    "email",
}


def normalize_email_candidate(email: str) -> str:
    email = str(email or "").strip().lower()

    email = email.replace("mailto:", "")
    email = email.strip(" ,;:()[]{}<>\"'")

    email = re.sub(r"^[^a-z0-9]+", "", email)
    email = re.sub(r"[^a-z0-9]+$", "", email)

    email = email.replace("..", ".")
    email = email.replace("@.", "@")
    email = email.replace(".@", "@")

    return email


def is_valid_recruiter_email(
    email: str,
    allow_free_email: bool = True,
    context_text: str = "",
) -> bool:

    email = normalize_email_candidate(email)

    if not email or "@" not in email:
        return False

    if len(email) < 6 or len(email) > 254:
        return False

    if not EMAIL_REGEX_STRICT.fullmatch(email):
        return False

    local, domain = email.rsplit("@", 1)

    domain = domain.lower().strip(".")
    local = local.lower().strip(".")

    if not local or not domain:
        return False

    if domain in BLOCKED_EMAIL_DOMAINS:
        return False

    if domain.startswith("-") or domain.endswith("-"):
        return False

    if ".." in domain or ".." in local or "_" in domain:
        return False

    labels = domain.split(".")

    if len(labels) < 2:
        return False

    if any(
        not label
        or label.startswith("-")
        or label.endswith("-")
        for label in labels
    ):
        return False

    if any(ch.isdigit() for ch in labels[-1]):
        return False

    tld = labels[-1]

    if tld in COMMON_BAD_TLDS:
        return False

    if tld not in VALID_TLDS:
        return False

    local_clean = re.sub(r"[^a-z]", "", local)

    if local_clean in BLOCKED_EMAIL_LOCAL_PARTS:
        return False

    bad_fragments = [
        "example",
        "yourname",
        "username",
        "firstlast",
        "firstname",
        "lastname",
        "sample",
        "dummy",
        "none",
        "null",
        "yourmail",
        "youremail",
    ]

    if any(fragment in local for fragment in bad_fragments):
        return False

    suspicious_local_parts = {
        "me",
        "email",
        "mail",
        "contact",
        "apply",
        "resume",
        "cv",
    }

    if local in suspicious_local_parts and domain not in FREE_EMAIL_DOMAINS:

        domain_root = labels[0]

        if len(labels) == 2 and not any(
            token in domain_root
            for token in (
                "staff",
                "talent",
                "recruit",
                "career",
                "job",
                "hr",
                "consult",
                "tech",
                "group",
            )
        ):
            return False

    if domain in FREE_EMAIL_DOMAINS:

        if not allow_free_email:
            return False

        allowed_free_prefixes = (
            "hr",
            "recruit",
            "recruiter",
            "recruiting",
            "talent",
            "careers",
            "jobs",
            "staffing",
            "hiring",
            "resume",
            "resumes",
            "vendor",
        )

        recruiting_context = any(
            term in str(context_text or "").lower()
            for term in (
                "hiring",
                "recruiter",
                "recruitment",
                "talent acquisition",
                "send resume",
                "share resume",
                "interested candidates",
                "job opening",
                "position",
                "requirement",
            )
        )

        # Split local part by common separators to check for allowed recruiter prefixes
        local_parts = re.split(r"[._%+-]", local)
        has_recruiter_prefix = any(
            part in allowed_free_prefixes
            for part in local_parts
        ) or local.startswith(allowed_free_prefixes)

        if not has_recruiter_prefix:

            if not recruiting_context:
                return False

            trailing_digits = re.search(r"(\d+)$", local)

            if trailing_digits and len(trailing_digits.group(1)) >= 3:
                return False

            if len(local) < 8:
                return False

    return True


def email_quality_score(email: str) -> int:

    email = normalize_email_candidate(email)

    if "@" not in email:
        return -100

    local, domain = email.rsplit("@", 1)

    score = 0

    if domain not in FREE_EMAIL_DOMAINS:
        score += 40
    else:
        score -= 10

    if local.startswith(
        (
            "recruit",
            "talent",
            "career",
            "jobs",
            "hr",
            "staffing",
            "hiring",
        )
    ):
        score += 25

    if any(
        token in domain
        for token in (
            "staff",
            "talent",
            "recruit",
            "career",
            "consult",
            "tech",
        )
    ):
        score += 15

    if re.search(r"\d{3,}$", local):
        score -= 25

    return score


def filter_valid_recruiter_emails(
    emails: List[str],
    context_text: str = "",
) -> List[str]:

    valid = []
    seen = set()

    for email in emails or []:

        clean_email = normalize_email_candidate(email)

        if not is_valid_recruiter_email(
            clean_email,
            context_text=context_text,
        ):
            logger.info(
                f"Invalid/bounce-risk email skipped: {email}"
            )
            continue

        if clean_email not in seen:
            seen.add(clean_email)
            valid.append(clean_email)

    valid.sort(
        key=email_quality_score,
        reverse=True,
    )

    return valid


def extract_valid_emails(text: str) -> List[str]:
    return filter_valid_recruiter_emails(
        extract_emails(text),
        context_text=text,
    )


# ============================================================
# CYBERSECURITY
# ============================================================

CYBER_TERMS = [
    "cybersecurity",
    "cyber security",
    "security analyst",
    "information security",
    "it security",
    "soc analyst",
    "soc",
    "security operations center",
    "siem",
    "splunk",
    "sentinel",
    "microsoft sentinel",
    "qradar",
    "wazuh",
    "incident response",
    "dfir",
    "threat intelligence",
    "threat hunting",
    "osint",
    "blue team",
    "vulnerability",
    "vulnerability management",
    "iam",
    "identity access",
    "grc",
    "risk",
    "security compliance",
    "cloud security",
    "aws security",
    "azure security",
    "endpoint security",
]


# ============================================================
# STRICT USA LOCATION SIGNALS
# ============================================================

US_COUNTRY_SIGNALS = [
    "united states",
    "united states of america",
    "u.s.a.",
    "u.s.a",
    "usa",
    "us-based",
    "us based",
    "us location",
    "us locations",
    "based in the us",
    "based in us",
    "within the us",
    "within us",
    "located in the us",
    "located in us",
    "authorized to work in the us",
    "us work authorization",
    "us work eligible",
    "remote us",
    "remote usa",
    "us remote",
    "usa remote",
]


# Full US state names.
US_STATE_NAMES = [
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


# State abbreviations are ONLY accepted when used as a
# location-style token, e.g. "NY", "CA", "TX".
US_STATE_ABBREVIATIONS = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
}


# Major US cities useful for explicit location detection.
US_CITY_SIGNALS = [
    "new york",
    "new york city",
    "los angeles",
    "san francisco",
    "san diego",
    "san jose",
    "sacramento",
    "chicago",
    "houston",
    "dallas",
    "austin",
    "fort worth",
    "san antonio",
    "phoenix",
    "philadelphia",
    "boston",
    "seattle",
    "denver",
    "atlanta",
    "miami",
    "orlando",
    "tampa",
    "washington dc",
    "washington, dc",
    "washington d.c.",
    "charlotte",
    "raleigh",
    "detroit",
    "minneapolis",
    "portland",
    "las vegas",
    "salt lake city",
    "nashville",
    "columbus",
    "indianapolis",
    "pittsburgh",
    "cleveland",
    "cincinnati",
    "st louis",
    "kansas city",
    "baltimore",
    "richmond",
    "norfolk",
    "newark",
    "jersey city",
    "hartford",
    "new haven",
]


# ============================================================
# FOREIGN COUNTRY / LOCATION SIGNALS
# ============================================================

NON_US_SIGNALS = [
    "india",
    "hyderabad",
    "bengaluru",
    "bangalore",
    "chennai",
    "pune",
    "mumbai",
    "delhi",
    "noida",
    "gurgaon",
    "gurugram",
    "kolkata",
    "ahmedabad",

    "pakistan",
    "karachi",
    "lahore",
    "islamabad",

    "bangladesh",
    "dhaka",

    "nepal",
    "kathmandu",

    "sri lanka",
    "colombo",

    "philippines",
    "manila",

    "malaysia",
    "kuala lumpur",

    "singapore",

    "indonesia",
    "jakarta",

    "united arab emirates",
    "uae",
    "dubai",
    "abu dhabi",

    "saudi arabia",
    "riyadh",

    "qatar",
    "doha",

    "kuwait",
    "oman",
    "bahrain",

    "ghana",
    "nigeria",
    "kenya",
    "south africa",
    "egypt",

    "canada",
    "toronto",
    "vancouver",
    "ontario",
    "alberta",
    "montreal",
    "calgary",

    "united kingdom",
    " uk ",
    "london",
    "england",
    "scotland",
    "wales",
    "ireland",
    "dublin",

    "australia",
    "sydney",
    "melbourne",
    "brisbane",

    "new zealand",

    "germany",
    "france",
    "netherlands",
    "poland",
    "romania",
    "spain",
    "italy",
]


GLOBAL_MASS_HIRING_TERMS = [
    "multiple global job openings",
    "global job openings",
    "multiple countries",
    "across usa, canada",
    "usa canada uk",
    "usa and canada",
    "usa and india",
    "usa and uk",
    "usa and australia",
    "us and canada",
    "us and india",
    "us and uk",
    "us and australia",
    "worldwide hiring",
    "hiring worldwide",
    "global hiring",
    "hire globally",
    "all industries",
    "all roles",
    "various positions",
    "multiple positions",
    "visa sponsorship available",
    "limited interview slots",
    "100+ openings",
]


# ============================================================
# USA DETECTION
# ============================================================

def _contains_term(text: str, term: str) -> bool:
    padded = f" {str(text or '').lower()} "
    return term in padded


def has_us_country_signal(text: str) -> bool:

    low = f" {str(text or '').lower()} "

    for signal in US_COUNTRY_SIGNALS:
        if signal in low:
            return True

    return False


def has_us_state_name_signal(text: str) -> bool:

    low = str(text or "").lower()

    for state in US_STATE_NAMES:

        # Require the state to appear as a complete phrase.
        pattern = rf"\b{re.escape(state)}\b"

        if re.search(pattern, low):
            return True

    return False


def has_us_city_signal(text: str) -> bool:

    low = str(text or "").lower()

    for city in US_CITY_SIGNALS:

        pattern = rf"\b{re.escape(city)}\b"

        if re.search(pattern, low):
            return True

    return False


def has_us_state_abbreviation_signal(text: str) -> bool:

    text = str(text or "")

    # Strong location patterns:
    #
    # New York, NY
    # NY, USA
    # NY - Remote
    # Location: NY
    # Location - CA
    # Based in TX
    #
    patterns = [
        r"\b(?:new york|los angeles|chicago|houston|dallas|austin|boston|"
        r"seattle|miami|atlanta|denver|phoenix|philadelphia|san francisco)"
        r"\s*,\s*[A-Z]{2}\b",

        r"\b(?:location|located|based|office|offices|onsite|hybrid|remote)"
        r"\s*[:\-]?\s*[A-Z]{2}\b",

        r"\b[A-Z]{2}\s*,\s*(?:USA|U\.S\.A?\.|United States)\b",

        r"\b[A-Z]{2}\s*[-/]\s*(?:USA|US)\b",

        r"\b(?:USA|US)\s*[-/]\s*[A-Z]{2}\b",
    ]

    for pattern in patterns:

        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            return True

    return False


def has_us_signal(text: str) -> bool:

    """
    Return True ONLY when the text contains an explicit US signal.

    Accepted:
    - United States
    - USA
    - US-based
    - US remote
    - US work authorization
    - US state names
    - Major US cities
    - Strong state abbreviation + location context

    NOT accepted:
    - remote alone
    - generic "US" appearing as a normal English word
    - email domain alone
    """

    if has_us_country_signal(text):
        return True

    if has_us_state_name_signal(text):
        return True

    if has_us_city_signal(text):
        return True

    if has_us_state_abbreviation_signal(text):
        return True

    return False


def has_non_us_signal(text: str) -> bool:

    low = f" {str(text or '').lower()} "

    for signal in NON_US_SIGNALS:

        if signal in low:
            return True

    return False


def has_global_mass_hiring_signal(text: str) -> bool:

    low = f" {str(text or '').lower()} "

    return any(
        term in low
        for term in GLOBAL_MASS_HIRING_TERMS
    )


def is_mixed_location_post(text: str) -> bool:

    """
    Reject posts that mention USA plus another country.

    Example:
    - Hiring in USA and Canada
    - USA + India openings
    - US / UK hiring
    """

    return (
        has_us_signal(text)
        and has_non_us_signal(text)
    )


def is_us_target_post(
    text: str,
    require_explicit_us: bool = True,
) -> bool:

    """
    STRICT USA-ONLY TARGETING.

    A post is accepted ONLY when:
      1. Explicit US location evidence exists.
      2. No foreign-country/location signal exists.
      3. No global/multi-country hiring language exists.

    Remote alone is NOT enough.
    """

    text = str(text or "")

    if not text.strip():
        return False

    low = f" {text.lower()} "

    # --------------------------------------------------------
    # Reject global hiring
    # --------------------------------------------------------

    if has_global_mass_hiring_signal(text):
        logger.info(
            "USA filter rejected global/mass-hiring post."
        )
        return False

    # --------------------------------------------------------
    # Reject foreign location
    # --------------------------------------------------------

    if has_non_us_signal(text):
        logger.info(
            "USA filter rejected foreign-location post."
        )
        return False

    # --------------------------------------------------------
    # Reject mixed-country content
    # --------------------------------------------------------

    if is_mixed_location_post(text):
        logger.info(
            "USA filter rejected mixed-location post."
        )
        return False

    # --------------------------------------------------------
    # Explicit US evidence is mandatory
    # --------------------------------------------------------

    if require_explicit_us:

        if not has_us_signal(text):
            logger.info(
                "USA filter rejected post with no explicit US signal."
            )
            return False

    return True


# ============================================================
# BROWSER HELPERS
# ============================================================

def _random_delay(
    min_sec: float = MIN_ACTION_DELAY,
    max_sec: float = MAX_ACTION_DELAY,
) -> None:

    time.sleep(
        random.uniform(
            min_sec,
            max_sec,
        )
    )


def create_driver() -> webdriver.Chrome:

    chrome_options = Options()

    if HEADLESS_MODE:
        chrome_options.add_argument(
            "--headless=new"
        )

    if CHROME_PROFILE_DIR:
        chrome_options.add_argument(
            f"--user-data-dir={CHROME_PROFILE_DIR}"
        )

    chrome_options.add_argument(
        "--no-sandbox"
    )

    chrome_options.add_argument(
        "--disable-dev-shm-usage"
    )

    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    chrome_options.add_argument(
        "--start-maximized"
    )

    chrome_options.add_argument(
        "--disable-notifications"
    )

    chrome_options.add_argument(
        "--disable-popup-blocking"
    )

    chrome_options.add_argument(
        "--remote-debugging-port=0"
    )

    chrome_options.add_experimental_option(
        "excludeSwitches",
        ["enable-automation"],
    )

    chrome_options.add_experimental_option(
        "useAutomationExtension",
        False,
    )

    driver = webdriver.Chrome(
        options=chrome_options
    )

    driver.implicitly_wait(1)

    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', "
            "{get: () => undefined})"
        )
    except Exception:
        pass

    logger.info(
        "Chrome WebDriver initialized successfully."
    )

    return driver


def driver_is_alive(
    driver: webdriver.Chrome,
) -> bool:

    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def restart_driver(
    old_driver: Optional[webdriver.Chrome] = None,
) -> webdriver.Chrome:

    try:
        if old_driver:
            old_driver.quit()
    except Exception:
        pass

    new_driver = create_driver()

    wait_for_manual_login(new_driver)

    return new_driver


def wait_for_manual_login(
    driver: webdriver.Chrome,
) -> bool:

    driver.get(
        "https://www.linkedin.com/feed/"
    )

    logger.info(
        "LinkedIn opened. Checking login session..."
    )

    print("\n" + "=" * 60)
    print("  LINKEDIN LOGIN CHECK")
    print("=" * 60)
    print("If login page opens, login manually once.")
    print("After login, script will auto-detect feed.")
    print("=" * 60)

    login_selectors = (
        "input[placeholder*='Search'], "
        "input.search-global-typeahead__input, "
        "a[href*='/feed/'], "
        "a[href*='/mynetwork/'], "
        "img.global-nav__me-photo, "
        ".global-nav, "
        ".scaffold-layout"
    )

    start_time = time.time()
    max_wait_seconds = 180

    while time.time() - start_time < max_wait_seconds:

        try:

            current_url = driver.current_url.lower()

            if (
                "login" not in current_url
                and "checkpoint" not in current_url
            ):

                try:

                    WebDriverWait(
                        driver,
                        5,
                    ).until(
                        EC.presence_of_element_located(
                            (
                                By.CSS_SELECTOR,
                                login_selectors,
                            )
                        )
                    )

                    logger.info(
                        "LinkedIn login verified successfully."
                    )

                    print(
                        "✅ LinkedIn login detected automatically!\n"
                    )

                    return True

                except TimeoutException:
                    pass

            print(
                "⏳ Waiting for LinkedIn login/session..."
            )

            time.sleep(5)

        except Exception:
            time.sleep(5)

    print(
        "⚠️ Could not verify LinkedIn login. "
        "Proceeding anyway...\n"
    )

    return True


# ============================================================
# SEARCH URLS
# ============================================================

def build_search_urls(
    keyword: str,
) -> List[str]:

    query_variants = [
        f'{keyword} "send resume"',
        f'{keyword} "email resume"',
        f'{keyword} "share resume"',
        f'{keyword} "interested candidates"',
        f"{keyword} recruiter email",
        f"{keyword} hiring email",
    ]

    urls = []

    for index, query in enumerate(
        query_variants
    ):

        encoded = quote_plus(query)

        if index < 4:

            url = (
                "https://www.linkedin.com/search/results/content/"
                f"?keywords={encoded}"
                f"&datePosted=%22past-month%22"
                f"&geoUrn=%5B%22103644278%22%5D"
                f"&origin=FACETED_SEARCH"
                f"&sortBy=%22date_posted%22"
            )

        else:

            url = (
                "https://www.linkedin.com/search/results/content/"
                f"?keywords={encoded}"
                f"&datePosted=%22past-month%22"
                f"&origin=FACETED_SEARCH"
                f"&sortBy=%22date_posted%22"
            )

        urls.append(url)

    return urls


def search_posts(
    driver: webdriver.Chrome,
    keyword: str,
    attempt: int = 0,
) -> None:

    urls = build_search_urls(keyword)

    attempt = min(
        attempt,
        len(urls) - 1,
    )

    logger.info(
        f"Searching LinkedIn posts for: "
        f"{keyword} | attempt={attempt + 1}"
    )

    driver.get(
        urls[attempt]
    )

    _random_delay(
        1.2,
        2.0,
    )


def page_has_no_results(
    driver: webdriver.Chrome,
) -> bool:

    try:
        text = driver.find_element(
            By.TAG_NAME,
            "body",
        ).text.lower()

    except Exception:
        return False

    no_result_terms = [
        "no results found",
        "try shortening or rephrasing your search",
        "no matching results",
        "we couldn’t find any results",
        "we couldn't find any results",
    ]

    return any(
        term in text
        for term in no_result_terms
    )


# ============================================================
# SCROLL
# ============================================================

def scroll_and_load_posts(
    driver: webdriver.Chrome,
) -> None:

    last_height = 0

    attempts = min(
        MAX_SCROLL_ATTEMPTS,
        FAST_SCROLL_ATTEMPTS,
    )

    for _ in range(attempts):

        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

        _random_delay(
            0.45,
            0.85,
        )

        new_height = driver.execute_script(
            "return document.body.scrollHeight"
        )

        if new_height == last_height:
            break

        last_height = new_height


# ============================================================
# SEE MORE
# ============================================================

def click_see_more_buttons(
    driver: webdriver.Chrome,
    root=None,
    limit=20,
) -> None:

    search_root = (
        root
        if root is not None
        else driver
    )

    xpaths = [
        ".//button[contains(translate(., "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz'), "
        "'see more')]",

        ".//span[contains(translate(., "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz'), "
        "'see more')]/ancestor::button",

        ".//button[contains(translate(., "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz'), "
        "'show more')]",

        ".//span[contains(translate(., "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz'), "
        "'show more')]/ancestor::button",
    ]

    clicked = 0

    for xpath in xpaths:

        try:

            buttons = search_root.find_elements(
                By.XPATH,
                xpath,
            )

            for btn in buttons[:limit]:

                try:

                    if (
                        btn.is_displayed()
                        and btn.is_enabled()
                    ):

                        driver.execute_script(
                            "arguments[0].scrollIntoView("
                            "{block: 'center'});",
                            btn,
                        )

                        time.sleep(0.05)

                        driver.execute_script(
                            "arguments[0].click();",
                            btn,
                        )

                        clicked += 1

                        time.sleep(0.08)

                except (
                    StaleElementReferenceException,
                    ElementClickInterceptedException,
                ):
                    continue

                except Exception:
                    continue

        except Exception:
            continue

    if clicked:
        logger.info(
            f"Clicked {clicked} see-more buttons."
        )


# ============================================================
# TEXT CLEANING
# ============================================================

def looks_like_page_dump(
    text: str,
) -> bool:

    text = str(text or "").strip()

    low = text.lower()

    if not text:
        return False

    if len(text) > 9000:
        return True

    bad_count = sum(
        1
        for term in PAGE_DUMP_TERMS
        if term in low
    )

    if bad_count >= 4 and len(text) > 2500:
        return True

    if bad_count >= 6:
        return True

    if (
        "are these results helpful" in low
        and "your feedback helps us improve" in low
        and len(text) > 1800
    ):
        return True

    return False


def is_reaction_or_engagement_line(
    line: str,
) -> bool:

    low = str(line or "").strip().lower()

    if not low:
        return True

    patterns = [
        r"^\d+\s+reaction[s]?$",
        r"^\d+\s+comment[s]?$",
        r"^\d+\s+repost[s]?$",
        r"^\d+\s+share[s]?$",
        r"^\d+\s+like[s]?$",
        r"^\d+\s+impression[s]?$",
        r"^like$",
        r"^comment$",
        r"^repost$",
        r"^send$",
        r"^share$",
        r"^\u2026\s*more$",
        r"^\.\.\.\s*more$",
    ]

    return any(
        re.fullmatch(
            pattern,
            low,
        )
        for pattern in patterns
    )


def clean_post_text(
    text: str,
    keep_newlines: bool = False,
) -> str:

    text = str(text or "")

    text = text.replace(
        "\r",
        "\n",
    ).replace(
        "\t",
        " ",
    )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    junk_exact = {
        "home",
        "my network",
        "jobs",
        "messaging",
        "notifications",
        "me",
        "for business",
        "try premium",
        "try premium for ₹0",
        "start premium",
        "posts",
        "latest",
        "past 24 hours",
        "content type",
        "from member",
        "all filters",
        "reset",
        "feed post",
        "like",
        "comment",
        "share",
        "repost",
        "send",
        "see more",
        "show more",
        "follow",
        "join",
        "connect",
        "are these results helpful?",
        "your feedback helps us improve search results",
        "about",
        "accessibility",
        "help center",
        "privacy & terms",
        "ad choices",
        "advertising",
        "business services",
        "get the linkedin app",
        "more",
    }

    cleaned_lines = []

    for line in lines:

        low = line.lower().strip()

        if is_reaction_or_engagement_line(line):
            continue

        if low in junk_exact:
            continue

        if re.fullmatch(
            r"\d+",
            low,
        ):
            continue

        if (
            "notifications home my network jobs messaging"
            in low
        ):
            continue

        if (
            "skip to search" in low
            or "skip to main content" in low
        ):
            continue

        if "linkedin corporation" in low:
            continue

        cleaned_lines.append(line)

    if keep_newlines:
        cleaned = "\n".join(
            cleaned_lines
        )
    else:
        cleaned = " ".join(
            cleaned_lines
        )

    cleaned = "\n".join(
        [
            " ".join(
                line.split()
            )
            for line in cleaned.splitlines()
        ]
    )

    if not keep_newlines:
        cleaned = " ".join(
            cleaned.split()
        )

    return cleaned.strip()


# ============================================================
# POST FILTERS
# ============================================================

def is_blocked_post(
    text: str,
) -> bool:

    text_lower = str(text).lower()

    return any(
        term in text_lower
        for term in BLOCKED_TERMS
    )


def is_relevant_job_post(
    text: str,
    keyword: str,
) -> bool:

    low = clean_post_text(
        text
    ).lower()

    key = clean_post_text(
        keyword
    ).lower()

    if not extract_valid_emails(text):
        return False

    if is_blocked_post(low):
        return False

    if not any(
        term in low
        for term in [
            "hiring",
            "opening",
            "opportunity",
            "position",
            "role",
            "requirement",
            "looking for",
            "send resume",
            "share resume",
            "email resume",
            "apply",
            "internship",
            "intern",
            "co-op",
            "coop",
        ]
    ):
        return False

    software_search = any(
        term in key
        for term in [
            "software",
            "developer",
            "engineer intern",
            "sde",
            "java",
            "python",
            "full stack",
            "frontend",
            "backend",
            "web",
            "computer science",
            "technology",
            "it intern",
            "data analyst",
            "data science",
            "power bi",
            "business intelligence",
            "qa",
            "testing",
            "cloud",
            "devops",
        ]
    )

    if software_search:

        technical_context = (
            any(
                term in low
                for term in SOFTWARE_INTERNSHIP_TERMS
            )
            or (
                any(
                    term in low
                    for term in [
                        "intern",
                        "internship",
                        "co-op",
                        "coop",
                        "entry level",
                        "new grad",
                    ]
                )
                and any(
                    term in low
                    for term in [
                        "software",
                        "developer",
                        "programming",
                        "computer science",
                        "java",
                        "python",
                        "javascript",
                        "frontend",
                        "backend",
                        "full stack",
                        "web development",
                        "application development",
                        "data analyst",
                        "data science",
                        "quality assurance",
                        "test engineer",
                        "cloud",
                        "devops",
                    ]
                )
            )
        )

        return technical_context

    positive_terms = (
        MARKETING_TERMS
        + CYBER_TERMS
    )

    keyword_words = [
        word
        for word in re.findall(
            r"[a-z]+",
            key,
        )
        if len(word) > 2
        and word not in {
            "email",
            "hiring",
            "opening",
            "role",
        }
    ]

    return (
        any(
            term in low
            for term in positive_terms
        )
        or any(
            word in low
            for word in keyword_words
        )
    )


# ============================================================
# POST ELEMENTS
# ============================================================

def find_post_elements(
    driver: webdriver.Chrome,
):

    selectors = [
        "li.reusable-search__result-container",
        "div.reusable-search__result-container",
        "div.entity-result",
        "li div.entity-result",
        "ul.reusable-search__entity-result-list > li",
        "div[data-urn*='urn:li:activity']",
        "div.feed-shared-update-v2",
        "article",
    ]

    elements = []

    seen_keys = set()

    def add_element(el):

        try:

            txt = (
                el.text
                or ""
            ).strip()

            if len(txt) < 40:
                return

            low = txt.lower()

            if (
                "@"
                not in txt
                and len(txt) < 120
            ):
                return

            if (
                "are these results helpful"
                in low
                and "your feedback helps us improve"
                in low
                and "@" not in txt
            ):
                return

            key = el.id

            if key not in seen_keys:

                seen_keys.add(key)
                elements.append(el)

        except Exception:
            return

    for selector in selectors:

        try:

            for el in driver.find_elements(
                By.CSS_SELECTOR,
                selector,
            ):
                add_element(el)

        except Exception:
            continue

    try:

        js_elements = driver.execute_script(
            r"""
            const emailRegex =
                /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i;

            const usefulWords = /(hiring|requirement|need|looking|contract|remote|hybrid|onsite|role|position|opening|cybersecurity|cyber security|security analyst|information security|soc analyst|siem|splunk|sentinel|wazuh|incident response|threat intelligence|threat hunting|vulnerability|iam|grc|cloud security|seo|digital marketing|ppc|google ads|sem|performance marketing|growth marketing|content marketing|email marketing|marketing automation|social media|lead generation)/i;

            const nodes =
                Array.from(
                    document.querySelectorAll('li, article, div')
                );

            const out = [];

            for (const node of nodes) {

                const txt =
                    (node.innerText || '').trim();

                if (!txt) continue;

                if (
                    txt.length < 80
                    || txt.length > 6500
                ) continue;

                if (!emailRegex.test(txt))
                    continue;

                if (!usefulWords.test(txt))
                    continue;

                const rect =
                    node.getBoundingClientRect();

                if (
                    rect.width < 250
                    || rect.height < 80
                ) continue;

                out.push(node);

                if (out.length >= 60)
                    break;
            }

            return out;
            """
        )

        for el in js_elements or []:
            add_element(el)

    except Exception:
        pass

    return elements


# ============================================================
# RECRUITER NAME
# ============================================================

def get_recruiter_name(
    post_el,
    post_text: str,
) -> str:

    selectors = [
        ".update-components-actor__name span[aria-hidden='true']",
        ".feed-shared-actor__name span[aria-hidden='true']",
        ".entity-result__title-text span[aria-hidden='true']",
        ".entity-result__title-text a span[dir='ltr']",
        "span.update-components-actor__name",
        "span.feed-shared-actor__name",
        "a.update-components-actor__meta-link span[dir='ltr']",
        "a.feed-shared-actor__container-link span[dir='ltr']",
        "a.app-aware-link[href*='/in/'] span[dir='ltr']",
        "a[href*='/in/'] span[dir='ltr']",
    ]

    bad_fragments = [
        "try premium",
        "premium for",
        "follow",
        "join",
        "connect",
        "message",
        "view profile",
        "linkedin",
        "posted",
        "repost",
        "like",
        "comment",
        "share",
        "send",
        "followers",
        "connections",
        "search",
    ]

    def valid_name(
        name: str,
    ) -> bool:

        name = clean_post_text(
            name
        )

        low = name.lower()

        if not name:
            return False

        if any(
            bad in low
            for bad in bad_fragments
        ):
            return False

        if (
            "@" in name
            or "http" in low
        ):
            return False

        if re.fullmatch(
            r"[\d\s+().-]+",
            name,
        ):
            return False

        if (
            len(name) < 3
            or len(name) > 80
        ):
            return False

        words = [
            w
            for w in re.split(
                r"\s+",
                name,
            )
            if w
        ]

        if len(words) > 8:
            return False

        return bool(
            re.search(
                r"[A-Za-z]",
                name,
            )
        )

    for selector in selectors:

        try:

            els = post_el.find_elements(
                By.CSS_SELECTOR,
                selector,
            )

            for name_el in els:

                name = clean_post_text(
                    name_el.text
                )

                if valid_name(name):
                    return name[:80]

        except Exception:
            continue

    lines = [
        line.strip()
        for line in str(
            post_text or ""
        ).splitlines()
        if line.strip()
    ]

    for line in lines[:15]:

        line = clean_post_text(
            line
        )

        if valid_name(line):
            return line[:80]

    return ""


# ============================================================
# PROFILE LINK
# ============================================================

def get_profile_link(
    post_el,
) -> str:

    selectors = [
        "a.update-components-actor__meta-link",
        "a.feed-shared-actor__container-link",
        "a.app-aware-link[href*='/in/']",
        "a[href*='linkedin.com/in/']",
    ]

    for selector in selectors:

        try:

            link_el = post_el.find_element(
                By.CSS_SELECTOR,
                selector,
            )

            href = (
                link_el.get_attribute(
                    "href"
                )
                or ""
            )

            if href and "/in/" in href:
                return href.split("?")[0]

        except Exception:
            continue

    return ""


# ============================================================
# POST URL
# ============================================================

def normalize_post_url(
    url: str,
) -> str:

    url = str(
        url or ""
    ).strip()

    if not url:
        return ""

    if (
        "urn:li:activity:" in url
        and "/feed/update/" not in url
    ):

        match = re.search(
            r"urn:li:activity:\d+",
            url,
        )

        if match:
            return (
                "https://www.linkedin.com/feed/update/"
                f"{match.group(0)}/"
            )

    return url.split("?")[0]


def is_valid_post_url(
    url: str,
) -> bool:

    url = str(
        url or ""
    ).lower()

    return (
        "/feed/update/" in url
        or "urn:li:activity" in url
        or "/posts/" in url
        or "activity-" in url
    ) and "/in/" not in url


def get_post_url(
    post_el,
) -> str:

    try:

        data_urn = (
            post_el.get_attribute(
                "data-urn"
            )
            or ""
        )

        if "urn:li:activity:" in data_urn:
            return normalize_post_url(
                data_urn
            )

    except Exception:
        pass

    try:

        descendants = post_el.find_elements(
            By.CSS_SELECTOR,
            "[data-urn*='urn:li:activity']",
        )

        for d in descendants:

            data_urn = (
                d.get_attribute(
                    "data-urn"
                )
                or ""
            )

            if "urn:li:activity:" in data_urn:
                return normalize_post_url(
                    data_urn
                )

    except Exception:
        pass

    selectors = [
        "a[href*='/feed/update/urn:li:activity']",
        "a[href*='urn:li:activity']",
        "a[href*='/posts/']",
        "a[href*='activity-']",
        "a[href*='/pulse/']",
    ]

    for selector in selectors:

        try:

            links = post_el.find_elements(
                By.CSS_SELECTOR,
                selector,
            )

            for link_el in links:

                href = (
                    link_el.get_attribute(
                        "href"
                    )
                    or ""
                ).strip()

                if (
                    href
                    and is_valid_post_url(href)
                ):
                    return normalize_post_url(
                        href
                    )

        except Exception:
            continue

    return ""


# ============================================================
# POST TIME
# ============================================================

def get_post_time(
    post_el,
) -> str:

    selectors = [
        ".update-components-actor__sub-description span",
        ".feed-shared-actor__sub-description",
        "time",
    ]

    for selector in selectors:

        try:

            time_el = post_el.find_element(
                By.CSS_SELECTOR,
                selector,
            )

            text = clean_post_text(
                time_el.text
            )

            if text:
                return text[:50]

        except Exception:
            continue

    return "Recent"


# ============================================================
# LOCATION DETECTION
# ============================================================

def detect_location(
    text: str,
) -> str:

    low = str(text).lower()

    # Country first
    if (
        "united states" in low
        or "usa" in low
        or "u.s.a" in low
        or "us-based" in low
        or "us based" in low
    ):
        if (
            "remote" in low
            or "wfh" in low
            or "work from home" in low
        ):
            return "Remote - United States"
        return "United States"

    # Major cities
    city_mapping = {
        "new york": "New York, NY",
        "chicago": "Chicago, IL",
        "houston": "Houston, TX",
        "dallas": "Dallas, TX",
        "austin": "Austin, TX",
        "san francisco": "San Francisco, CA",
        "los angeles": "Los Angeles, CA",
        "san diego": "San Diego, CA",
        "seattle": "Seattle, WA",
        "boston": "Boston, MA",
        "miami": "Miami, FL",
        "atlanta": "Atlanta, GA",
        "denver": "Denver, CO",
        "phoenix": "Phoenix, AZ",
        "philadelphia": "Philadelphia, PA",
        "newark": "Newark, NJ",
        "jersey city": "Jersey City, NJ",
        "hartford": "Hartford, CT",
        "new haven": "New Haven, CT",
    }

    for city, location in city_mapping.items():

        if city in low:
            return location

    state_mapping = {
        "california": "California",
        "texas": "Texas",
        "new jersey": "New Jersey",
        "connecticut": "Connecticut",
        "florida": "Florida",
        "virginia": "Virginia",
        "maryland": "Maryland",
        "massachusetts": "Massachusetts",
        "illinois": "Illinois",
        "washington": "Washington",
        "arizona": "Arizona",
        "colorado": "Colorado",
        "pennsylvania": "Pennsylvania",
        "ohio": "Ohio",
        "michigan": "Michigan",
        "north carolina": "North Carolina",
        "georgia": "Georgia",
        "minnesota": "Minnesota",
        "tennessee": "Tennessee",
        "nevada": "Nevada",
    }

    for state, location in state_mapping.items():

        if state in low:
            return location

    # Check for US State Abbreviations (e.g. CA, NY, TX, NJ)
    for abbrev in US_STATE_ABBREVIATIONS:
        pattern = rf"\b{abbrev}\b"
        if re.search(pattern, text):
            return f"{abbrev}, USA"

    if (
        "remote us" in low
        or "remote usa" in low
        or "us remote" in low
    ):
        return "Remote - United States"

    # Fallback for post text carrying general verified US signal
    if has_us_signal(text):
        if (
            "remote" in low
            or "wfh" in low
            or "work from home" in low
        ):
            return "Remote - United States"
        return "United States"

    return "Unknown"


# ============================================================
# POST TYPE
# ============================================================

def detect_post_type(
    text: str,
) -> str:

    low = str(text).lower()

    if (
        "bench sales" in low
        or "bench sale" in low
    ):
        return "Bench Sales"

    if (
        "hotlist" in low
        or "hot list" in low
        or "hotlists" in low
    ):
        return "Hotlist"

    if (
        "vendor list" in low
        or "vendor" in low
    ):
        return "Vendor"

    if (
        "w2" in low
        or "w-2" in low
    ):
        return "W2"

    if (
        "c2c" in low
        or "corp to corp" in low
    ):
        return "C2C"

    if "contract" in low:
        return "Contract"

    return "Recruiter Post"


# ============================================================
# TEXT EXTRACTION
# ============================================================

def get_text_from_element(
    driver: webdriver.Chrome,
    element,
) -> str:

    try:

        click_see_more_buttons(
            driver,
            root=element,
            limit=3,
        )

    except Exception:
        pass

    text_selectors = [
        ".update-components-text",
        ".feed-shared-inline-show-more-text",
        ".feed-shared-update-v2__description",
        ".entity-result__content",
        ".entity-result__summary",
        ".entity-result__primary-subtitle",
        ".entity-result__secondary-subtitle",
    ]

    texts = []

    for selector in text_selectors:

        try:

            els = element.find_elements(
                By.CSS_SELECTOR,
                selector,
            )

            for el in els:

                txt = driver.execute_script(
                    "return arguments[0].innerText;",
                    el,
                ) or el.text

                txt = clean_post_text(
                    txt,
                    keep_newlines=True,
                )

                if (
                    txt
                    and not looks_like_page_dump(txt)
                ):
                    texts.append(txt)

        except Exception:
            continue

    try:

        full_card_text = driver.execute_script(
            "return arguments[0].innerText;",
            element,
        ) or element.text

        full_card_text = clean_post_text(
            full_card_text,
            keep_newlines=True,
        )

        if (
            full_card_text
            and not looks_like_page_dump(
                full_card_text
            )
        ):
            texts.append(
                full_card_text
            )

    except Exception:
        pass

    if not texts:
        return ""

    def score_text(
        txt: str,
    ) -> int:

        low = txt.lower()

        score = 0

        score += (
            25
            if extract_valid_emails(txt)
            else 0
        )

        score += (
            10
            if "hiring" in low
            else 0
        )

        score += (
            8
            if "requirement" in low
            else 0
        )

        score += (
            8
            if any(
                term in low
                for term in (
                    MARKETING_TERMS
                    + CYBER_TERMS
                )
            )
            else 0
        )

        score += (
            5
            if "contract" in low
            else 0
        )

        score += (
            5
            if "remote" in low
            else 0
        )

        score += min(
            len(txt),
            2500,
        ) // 100

        score -= (
            25
            if looks_like_page_dump(txt)
            else 0
        )

        return score

    best = max(
        texts,
        key=score_text,
    )

    if len(best) > 3500:
        best = extract_single_email_block(
            best,
            "",
        )

    if len(best) > 3200:
        best = best[
            :3200
        ].rsplit(
            "\n",
            1,
        )[0].strip()

    return best.strip()


# ============================================================
# DETAIL PAGE
# ============================================================

def get_detail_page_text(
    driver: webdriver.Chrome,
    post_url: str,
) -> str:

    if not is_valid_post_url(
        post_url
    ):
        return ""

    original_window = (
        driver.current_window_handle
    )

    try:

        driver.execute_script(
            "window.open(arguments[0], '_blank');",
            post_url,
        )

        time.sleep(1.2)

        driver.switch_to.window(
            driver.window_handles[-1]
        )

        _random_delay(
            1.8,
            2.5,
        )

        click_see_more_buttons(
            driver,
            limit=5,
        )

        _random_delay(
            0.5,
            0.8,
        )

        selectors = [
            "div[data-urn*='urn:li:activity'] .update-components-text",
            "div[data-urn*='urn:li:activity'] .feed-shared-inline-show-more-text",
            ".feed-shared-update-v2 .update-components-text",
            ".feed-shared-update-v2 .feed-shared-inline-show-more-text",
            ".update-components-text",
            ".feed-shared-inline-show-more-text",
        ]

        texts = []

        for selector in selectors:

            try:

                elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    selector,
                )

                for el in elements:

                    try:

                        txt = driver.execute_script(
                            "return arguments[0].innerText;",
                            el,
                        ) or el.text

                        txt = clean_post_text(
                            txt,
                            keep_newlines=True,
                        )

                        if (
                            txt
                            and not looks_like_page_dump(
                                txt
                            )
                        ):
                            texts.append(txt)

                    except Exception:
                        continue

            except Exception:
                continue

        if not texts:
            return ""

        return max(
            texts,
            key=len,
        )

    except Exception as e:

        logger.warning(
            f"Could not fetch detail page text: {e}"
        )

        return ""

    finally:

        try:

            if len(
                driver.window_handles
            ) > 1:
                driver.close()

            driver.switch_to.window(
                original_window
            )

        except Exception:
            pass


# ============================================================
# EMAIL BLOCK
# ============================================================

def extract_single_email_block(
    text: str,
    keyword: str,
) -> str:

    text = clean_post_text(
        text,
        keep_newlines=True,
    )

    if not text:
        return ""

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    emails = extract_valid_emails(
        text
    )

    if not emails:
        return text

    email_positions = []

    for idx, line in enumerate(
        lines
    ):

        if extract_valid_emails(line):
            email_positions.append(idx)

    if not email_positions:
        return text

    keyword_words = [
        w.lower()
        for w in keyword.split()
        if len(w) > 2
    ]

    best_block = ""
    best_score = -1

    for email_idx in email_positions:

        start = max(
            0,
            email_idx - 28,
        )

        end = min(
            len(lines),
            email_idx + 12,
        )

        block_lines = lines[
            start:end
        ]

        while block_lines and (
            "try premium"
            in block_lines[0].lower()
            or re.fullmatch(
                r"\d+",
                block_lines[0].lower(),
            )
            or "3rd+"
            in block_lines[0].lower()
            or block_lines[0].lower()
            in {
                "follow",
                "join",
                "connect",
            }
        ):
            block_lines.pop(0)

        block = "\n".join(
            block_lines
        )

        low = block.lower()

        score = 0

        score += sum(
            3
            for w in keyword_words
            if w in low
        )

        score += (
            6
            if "hiring" in low
            else 0
        )

        score += (
            6
            if "requirement" in low
            else 0
        )

        score += (
            6
            if any(
                term in low
                for term in (
                    MARKETING_TERMS
                    + CYBER_TERMS
                )
            )
            else 0
        )

        score += (
            3
            if "location" in low
            else 0
        )

        score += (
            3
            if "experience" in low
            else 0
        )

        score += (
            3
            if (
                "interested" in low
                or "share" in low
            )
            else 0
        )

        score -= (
            10
            if "try premium" in low
            else 0
        )

        score -= (
            10
            if "are these results helpful"
            in low
            else 0
        )

        if score > best_score:

            best_score = score
            best_block = block

    best_block = clean_post_text(
        best_block,
        keep_newlines=True,
    )

    if len(best_block) > 3000:

        best_block = best_block[
            :3000
        ].rsplit(
            "\n",
            1,
        )[0].strip()

    return best_block


def choose_best_text(
    base_text: str,
    detail_text: str,
    keyword: str,
) -> str:

    base_clean = clean_post_text(
        base_text,
        keep_newlines=True,
    )

    detail_clean = clean_post_text(
        detail_text,
        keep_newlines=True,
    )

    candidates = []

    for txt in [
        base_clean,
        detail_clean,
    ]:

        if (
            txt
            and not looks_like_page_dump(
                txt
            )
        ):
            candidates.append(txt)

    if not candidates:

        if base_clean:
            return extract_single_email_block(
                base_clean,
                keyword,
            )

        if detail_clean:
            return extract_single_email_block(
                detail_clean,
                keyword,
            )

        return ""

    best = max(
        candidates,
        key=len,
    )

    if (
        len(best) > 3500
        or len(extract_emails(best)) > 2
    ):
        best = extract_single_email_block(
            best,
            keyword,
        )

    return best.strip()


# ============================================================
# LEAD SCORE
# ============================================================

def calculate_lead_score(
    text: str,
    keyword: str,
) -> int:

    low = str(
        text or ""
    ).lower()

    score = 45

    positive_weights = {
        "hiring": 18,
        "requirement": 16,
        "requirements": 16,
        "need": 12,
        "looking for": 14,
        "role": 8,
        "position": 8,
        "opening": 10,
        "opportunity": 8,
        "remote": 8,
        "contract": 8,
        "immediate": 6,
        "share resume": 12,
        "send resume": 12,
        "email": 6,

        "seo": 22,
        "seo specialist": 24,
        "seo executive": 22,
        "digital marketing": 22,
        "marketing specialist": 20,
        "marketing executive": 18,
        "marketing coordinator": 18,
        "ppc": 22,
        "google ads": 22,
        "sem": 20,
        "performance marketing": 22,
        "growth marketing": 20,
        "content marketing": 18,
        "email marketing": 18,
        "marketing automation": 18,
        "social media": 18,
        "lead generation": 18,

        "cybersecurity": 24,
        "cyber security": 24,
        "security analyst": 24,
        "information security": 22,
        "soc analyst": 26,
        "siem": 24,
        "splunk": 24,
        "sentinel": 22,
        "wazuh": 20,
        "incident response": 24,
        "threat intelligence": 24,
        "threat hunting": 22,
        "vulnerability": 22,
        "iam": 20,
        "grc": 20,
        "cloud security": 22,
    }

    negative_weights = {
        "bench sales": 60,
        "bench recruiter": 60,
        "bench marketing": 60,
        "hotlist": 70,
        "hot list": 70,
        "vendor list": 65,
        "available candidates": 65,
        "available consultants": 65,
        "share hotlist": 75,
        "requirements & hotlist": 75,
        "requirements and hotlist": 75,
        "training and placement": 60,
        "placement support": 60,
        "pay after placement": 70,
        "proxy interview": 80,
    }

    for term, weight in positive_weights.items():

        if term in low:
            score += weight

    for term, weight in negative_weights.items():

        if term in low:
            score -= weight

    keyword_words = [
        w
        for w in str(
            keyword or ""
        ).lower().split()
        if len(w) > 2
        and w not in {
            "email",
            "hiring",
            "specialist",
        }
    ]

    score += sum(
        5
        for w in keyword_words
        if w in low
    )

    if extract_valid_emails(text):
        score += 15

    if has_us_signal(text):
        score += 10

    if len(text) < 100:
        score -= 15

    if looks_like_page_dump(text):
        score -= 80

    return max(
        0,
        min(
            100,
            score,
        ),
    )


# ============================================================
# SINGLE POST PARSER
# ============================================================

def _parse_single_post(
    driver: webdriver.Chrome,
    post_el,
    keyword: str,
    index: int,
) -> Optional[Dict]:

    raw_text = get_text_from_element(
        driver,
        post_el,
    )

    if not raw_text:
        return None

    if not extract_valid_emails(
        raw_text
    ):
        return None

    profile_link = get_profile_link(
        post_el
    )

    post_url = get_post_url(
        post_el
    )

    detail_text = ""

    full_post_text = choose_best_text(
        raw_text,
        detail_text,
        keyword,
    )

    full_post_text = clean_post_text(
        full_post_text,
        keep_newlines=True,
    )

    if len(full_post_text) > 3200:

        full_post_text = extract_single_email_block(
            full_post_text,
            keyword,
        )

    if len(full_post_text) > 3000:

        full_post_text = full_post_text[
            :3000
        ].rsplit(
            "\n",
            1,
        )[0].strip()

    post_text_compact = clean_post_text(
        full_post_text
    )

    if (
        not post_text_compact
        or len(post_text_compact) < 40
    ):
        return None

    if looks_like_page_dump(
        post_text_compact
    ):
        logger.info(
            f"Post #{index + 1}: "
            "Page dump detected, skipped."
        )
        return None

    if is_blocked_post(
        post_text_compact
    ):
        logger.info(
            f"Post #{index + 1}: "
            "Spam/irrelevant blocked."
        )
        return None

    # ========================================================
    # CRITICAL USA-ONLY CHECK
    # ========================================================

    if not is_us_target_post(
        post_text_compact,
        require_explicit_us=True,
    ):
        logger.info(
            f"Post #{index + 1}: "
            "NON-USA post rejected."
        )
        return None

    emails = extract_valid_emails(
        post_text_compact
    )

    if not emails:
        return None

    if not is_relevant_job_post(
        post_text_compact,
        keyword,
    ):
        logger.info(
            f"Post #{index + 1}: "
            "Not relevant, skipped."
        )
        return None

    lead_score = calculate_lead_score(
        post_text_compact,
        keyword,
    )

    if lead_score < 55:

        logger.info(
            f"Post #{index + 1}: "
            f"Low lead score {lead_score}, skipped."
        )

        return None

    recruiter_name = get_recruiter_name(
        post_el,
        raw_text,
    )

    post_time = get_post_time(
        post_el
    )

    location = detect_location(
        post_text_compact
    )

    post_type = detect_post_type(
        post_text_compact
    )

    if not is_valid_post_url(
        post_url
    ):
        post_url = ""

    return {
        "recruiter_name": recruiter_name,
        "emails": ", ".join(emails),
        "profile_link": profile_link,
        "post_url": post_url,
        "post_time": post_time,
        "post_type": post_type,
        "job_role": keyword,
        "location": location,
        "full_post_text": full_post_text,
        "post_snippet": post_text_compact[:700].strip(),
        "lead_score": lead_score,
        "scraped_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }


# ============================================================
# FAST PAGE EXTRACTION
# ============================================================

def _email_context_blocks_from_page(
    driver: webdriver.Chrome,
    keyword: str,
    max_blocks: int = FAST_PAGE_BLOCK_LIMIT,
) -> List[str]:

    try:

        blocks = driver.execute_script(
            r"""
            const maxBlocks = arguments[0];

            const nodes =
                Array.from(
                    document.querySelectorAll(
                        'li, article, div, span'
                    )
                );

            const emailRegex =
                /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/ig;

            const usefulWords = /(hiring|requirement|requirements|need|looking|role|position|opening|opportunity|contract|remote|hybrid|onsite|send resume|share resume|email resume|interested candidates|cybersecurity|cyber security|security analyst|information security|soc analyst|soc l1|soc l2|security operations center|security monitoring|siem|splunk|sentinel|microsoft sentinel|qradar|wazuh|edr|xdr|incident response|dfir|threat intelligence|threat hunting|osint|blue team|vulnerability|vulnerability management|iam|identity access|active directory|grc|cloud security|cyber risk|seo|digital marketing|ppc|google ads|sem|performance marketing|growth marketing|content marketing|email marketing|marketing automation|social media|lead generation)/i;

            const out = [];
            const seen = new Set();

            for (const node of nodes) {

                const txt =
                    (node.innerText || '').trim();

                if (!txt)
                    continue;

                if (
                    txt.length < 50
                    || txt.length > 5500
                )
                    continue;

                if (!emailRegex.test(txt))
                    continue;

                emailRegex.lastIndex = 0;

                if (!usefulWords.test(txt))
                    continue;

                const rect =
                    node.getBoundingClientRect();

                if (
                    rect.width < 180
                    || rect.height < 35
                )
                    continue;

                const compact =
                    txt
                    .replace(/\s+/g, ' ')
                    .slice(0, 1200);

                if (seen.has(compact))
                    continue;

                seen.add(compact);

                out.push(txt);

                if (
                    out.length >= maxBlocks
                )
                    break;
            }

            const bodyText =
                (
                    document.body.innerText
                    || ''
                ).trim();

            const matches =
                Array.from(
                    bodyText.matchAll(
                        emailRegex
                    )
                );

            for (const m of matches) {

                if (
                    out.length >= maxBlocks
                )
                    break;

                const idx =
                    m.index || 0;

                const start =
                    Math.max(
                        0,
                        idx - 1200
                    );

                const end =
                    Math.min(
                        bodyText.length,
                        idx + 900
                    );

                const block =
                    bodyText
                    .slice(start, end)
                    .trim();

                if (
                    !block
                    || !usefulWords.test(block)
                )
                    continue;

                const compact =
                    block
                    .replace(/\s+/g, ' ')
                    .slice(0, 1200);

                if (seen.has(compact))
                    continue;

                seen.add(compact);
                out.push(block);
            }

            return out;
            """,
            max_blocks,
        )

    except Exception:
        blocks = []

    cleaned_blocks = []
    seen = set()

    for block in blocks or []:

        block = clean_post_text(
            block,
            keep_newlines=True,
        )

        if (
            not block
            or looks_like_page_dump(block)
        ):
            continue

        block = extract_single_email_block(
            block,
            keyword,
        )

        compact = clean_post_text(
            block
        )

        if (
            not compact
            or compact in seen
        ):
            continue

        if len(compact) < 60:
            continue

        seen.add(compact)

        cleaned_blocks.append(
            block
        )

    return cleaned_blocks


# ============================================================
# PAGE LEVEL LEADS
# ============================================================

def extract_page_level_leads(
    driver: webdriver.Chrome,
    keyword: str,
    require_explicit_us: bool = True,
) -> List[Dict]:

    leads = []

    seen_emails = set()

    blocks = _email_context_blocks_from_page(
        driver,
        keyword,
    )

    for idx, block in enumerate(
        blocks
    ):

        compact = clean_post_text(
            block
        )

        emails = extract_valid_emails(
            compact
        )

        if not emails:
            continue

        if is_blocked_post(
            compact
        ):
            continue

        # ====================================================
        # FINAL STRICT USA CHECK
        # ====================================================

        if not is_us_target_post(
            compact,
            require_explicit_us=True,
        ):

            logger.info(
                f"Page block #{idx + 1}: "
                "NON-USA/global location skipped."
            )

            continue

        if not is_relevant_job_post(
            compact,
            keyword,
        ):
            continue

        lead_score = calculate_lead_score(
            compact,
            keyword,
        )

        # Keep this stricter than old 12 threshold.
        if lead_score < 55:

            logger.info(
                f"Page block #{idx + 1}: "
                f"Low lead score {lead_score}, skipped."
            )

            continue

        new_emails = []

        for email in emails:

            email_low = (
                email.strip().lower()
            )

            if (
                email_low
                and email_low not in seen_emails
            ):

                seen_emails.add(
                    email_low
                )

                new_emails.append(
                    email_low
                )

        if not new_emails:
            continue

        leads.append(
            {
                "recruiter_name": "LinkedIn Recruiter",
                "emails": ", ".join(
                    new_emails
                ),
                "profile_link": "",
                "post_url": "",
                "post_time": "Recent",
                "post_type": detect_post_type(
                    compact
                ),
                "job_role": keyword,
                "location": detect_location(
                    compact
                ),
                "full_post_text": block[
                    :3000
                ].strip(),
                "post_snippet": compact[
                    :700
                ].strip(),
                "lead_score": lead_score,
                "scraped_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )

    if leads:

        logger.info(
            f"Fast page-level extraction found "
            f"{len(leads)} USA lead(s) for keyword: "
            f"{keyword}"
        )

    return leads


# ============================================================
# DEEP POST EXTRACTION
# ============================================================

def extract_post_data(
    driver: webdriver.Chrome,
    keyword: str,
) -> List[Dict]:

    posts_data = []

    seen_email_items = set()

    try:

        click_see_more_buttons(
            driver,
            limit=10,
        )

        _random_delay(
            0.8,
            1.4,
        )

        post_elements = find_post_elements(
            driver
        )

        logger.info(
            f"Found {len(post_elements)} "
            "potential post elements."
        )

        scan_limit = min(
            DEEP_SCAN_POST_LIMIT,
            EFFECTIVE_MAX_POSTS_PER_KEYWORD,
        )

        logger.info(
            f"Processing first "
            f"{scan_limit} posts for keyword: "
            f"{keyword}"
        )

        for idx, post_el in enumerate(
            post_elements[:scan_limit]
        ):

            try:

                post_info = _parse_single_post(
                    driver,
                    post_el,
                    keyword,
                    idx,
                )

                if (
                    post_info
                    and post_info.get("emails")
                ):

                    emails = [
                        e.strip().lower()
                        for e in post_info[
                            "emails"
                        ].split(",")
                        if e.strip()
                    ]

                    new_emails = [
                        e
                        for e in emails
                        if e not in seen_email_items
                    ]

                    if not new_emails:

                        logger.info(
                            f"Post #{idx + 1}: "
                            "Duplicate emails skipped."
                        )

                        continue

                    for e in new_emails:
                        seen_email_items.add(e)

                    post_info[
                        "emails"
                    ] = ", ".join(
                        new_emails
                    )

                    posts_data.append(
                        post_info
                    )

                    jd_len = len(
                        post_info.get(
                            "full_post_text",
                            "",
                        )
                    )

                    logger.info(
                        f"Post #{idx + 1}: "
                        f"Found {post_info['post_type']} "
                        f"email(s): {post_info['emails']} | "
                        f"Score: {post_info.get('lead_score', 'NA')} | "
                        f"JD chars: {jd_len} | "
                        f"Recruiter: "
                        f"{post_info.get('recruiter_name', '')}"
                    )

            except StaleElementReferenceException:

                logger.warning(
                    f"Post #{idx + 1}: "
                    "Element stale, skipping."
                )

            except Exception as e:

                logger.warning(
                    f"Post #{idx + 1}: "
                    f"Error parsing — {e}"
                )

    except Exception as e:

        logger.error(
            f"Error extracting posts: {e}"
        )

    return posts_data


# ============================================================
# KEYWORD FALLBACK SCRAPER
# ============================================================

def scrape_keyword_with_fallback(
    driver: webdriver.Chrome,
    keyword: str,
) -> List[Dict]:

    """
    STRICT USA-ONLY FAST MODE.

    Every search attempt:
        1. LinkedIn USA geo filter where available.
        2. Explicit US validation.
        3. Foreign location rejection.
        4. Global/multi-country rejection.
        5. Email validation.
        6. Job relevance validation.
        7. Lead score validation.
    """

    labels = [
        'US Past Month + "send resume"',
        'US Past Month + "email resume"',
        'US Past Month + "share resume"',
        'US Past Month + "interested candidates"',
        "Past Month + Recruiter Email + Explicit US",
        "Past Month + Hiring Email + Explicit US",
    ]

    all_attempt_posts = []

    seen_attempt_emails = set()

    def add_posts(
        posts: List[Dict],
    ) -> int:

        added = 0

        for post in posts or []:

            emails = [
                e.strip().lower()
                for e in post.get(
                    "emails",
                    "",
                ).split(",")
                if e.strip()
            ]

            new_emails = [
                e
                for e in emails
                if e not in seen_attempt_emails
            ]

            if not new_emails:
                continue

            for e in new_emails:

                seen_attempt_emails.add(
                    e
                )

            post[
                "emails"
            ] = ", ".join(
                new_emails
            )

            all_attempt_posts.append(
                post
            )

            added += 1

        return added

    for attempt, label in enumerate(
        labels
    ):

        print(
            f"   Filter: {label}"
        )

        if not driver_is_alive(
            driver
        ):
            raise WebDriverException(
                "Driver session is not alive"
            )

        try:

            search_posts(
                driver,
                keyword,
                attempt=attempt,
            )

            scroll_and_load_posts(
                driver
            )

            click_see_more_buttons(
                driver,
                limit=15,
            )

        except Exception as e:

            logger.warning(
                f"Driver session lost or "
                f"page load failed: {e}"
            )

            raise

        if SAVE_SEARCH_SCREENSHOTS:

            try:

                screenshot_path = (
                    SCREENSHOTS_DIR
                    / f"search_"
                    f"{keyword.replace(' ', '_')}"
                    f"_try{attempt + 1}.png"
                )

                driver.save_screenshot(
                    str(screenshot_path)
                )

                logger.info(
                    f"Screenshot saved: "
                    f"{screenshot_path}"
                )

            except Exception:
                pass

        if page_has_no_results(
            driver
        ):

            print(
                f"   ⚠️ No posts visible "
                f"for {label}."
            )

            continue

        # ====================================================
        # STRICT USA-ONLY EXTRACTION
        # ====================================================

        fast_posts = extract_page_level_leads(
            driver,
            keyword,
            require_explicit_us=True,
        )

        fast_added = add_posts(
            fast_posts
        )

        if fast_added:

            print(
                f"   ⚡ Fast USA-only extraction "
                f"added {fast_added} lead(s)."
            )

        else:

            print(
                f"   ⚠️ No USA-only email leads "
                f"for {label}. Moving to next filter..."
            )

    if all_attempt_posts:

        print(
            f"   ✅ Fast mode collected "
            f"{len(all_attempt_posts)} "
            f"UNIQUE USA lead(s) "
            f"for '{keyword}'"
        )

    else:

        print(
            f"   ⚠️ Fast mode found "
            f"0 valid USA leads "
            f"for '{keyword}'"
        )

    return all_attempt_posts


# ============================================================
# MAIN SCRAPER
# ============================================================

def scrape_linkedin_posts(
    keywords: Optional[List[str]] = None,
) -> List[Dict]:

    if keywords is None:

        from config import DEFAULT_SEARCH_KEYWORDS

        keywords = DEFAULT_SEARCH_KEYWORDS

    all_posts = []

    global_seen_emails = set()

    driver = None

    try:

        driver = create_driver()

        if not wait_for_manual_login(
            driver
        ):

            logger.error(
                "LinkedIn login failed. "
                "Aborting scrape."
            )

            return []

        for keyword in keywords:

            print(
                f"\n🔍 Searching LinkedIn "
                f"USA-only posts for: "
                f"'{keyword}'"
            )

            logger.info(
                f"Processing USA-only keyword: "
                f"{keyword}"
            )

            if not driver_is_alive(
                driver
            ):

                logger.warning(
                    "Driver is dead before keyword. "
                    "Restarting Chrome..."
                )

                driver = restart_driver(
                    driver
                )

            try:

                posts = scrape_keyword_with_fallback(
                    driver,
                    keyword,
                )

            except Exception as e:

                logger.warning(
                    f"Keyword '{keyword}' failed "
                    f"due to browser/session issue: {e}"
                )

                try:

                    print(
                        "   🔁 Restarting LinkedIn "
                        "browser session and retrying "
                        "keyword once..."
                    )

                    driver = restart_driver(
                        driver
                    )

                    posts = scrape_keyword_with_fallback(
                        driver,
                        keyword,
                    )

                except Exception as retry_error:

                    logger.error(
                        f"Retry failed for keyword "
                        f"'{keyword}': {retry_error}"
                    )

                    posts = []

            unique_posts = []

            for post in posts:

                # =================================================
                # FINAL SAFETY CHECK
                # =================================================

                post_text = post.get(
                    "full_post_text",
                    "",
                )

                if not is_us_target_post(
                    post_text,
                    require_explicit_us=True,
                ):

                    logger.warning(
                        "FINAL USA SAFETY CHECK "
                        "rejected a non-USA post."
                    )

                    continue

                emails = [
                    e.strip().lower()
                    for e in post.get(
                        "emails",
                        "",
                    ).split(",")
                    if e.strip()
                ]

                new_emails = [
                    e
                    for e in emails
                    if e not in global_seen_emails
                ]

                if not new_emails:
                    continue

                for e in new_emails:

                    global_seen_emails.add(
                        e
                    )

                post[
                    "emails"
                ] = ", ".join(
                    new_emails
                )

                # Force location field to remain US-related.
                detected_location = detect_location(
                    post_text
                )

                if (
                    detected_location
                    == "Unknown"
                ):

                    logger.warning(
                        "Final location check "
                        "rejected unknown location."
                    )

                    continue

                post[
                    "location"
                ] = detected_location

                unique_posts.append(
                    post
                )

            all_posts.extend(
                unique_posts
            )

            print(
                f"   ✅ Found "
                f"{len(unique_posts)} "
                f"UNIQUE USA posts with "
                f"valid emails for "
                f"'{keyword}'"
            )

            _random_delay(
                1,
                2,
            )

    except Exception as e:

        logger.error(
            f"Scraping error: {e}"
        )

    finally:

        if driver:

            print(
                "\n🔒 Closing browser..."
            )

            try:
                driver.quit()
            except Exception:
                pass

    logger.info(
        f"Total unique USA-only "
        f"posts with emails found: "
        f"{len(all_posts)}"
    )

    return all_posts