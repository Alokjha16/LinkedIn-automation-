"""
email_extractor.py - Recruiter Email Extraction and Validation

Goals:
- Extract normal and obfuscated email addresses
- Reject broken LinkedIn text fragments such as:
    me@keerti.pandey
    resume@sakshi.aswal
- Reject placeholder, disposable, typo and non-recruiter addresses
- Preserve valid company-domain and recruiter mailbox addresses
- Maintain compatibility with existing linkedin_scraper.py
"""

import logging
import re
from typing import List, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# EMAIL REGEX
# ============================================================

EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+\-])"
    r"[A-Za-z0-9][A-Za-z0-9._%+\-]{0,63}"
    r"@"
    r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)+"
    r"(?![A-Za-z0-9._%+\-])",
    re.IGNORECASE,
)


# ============================================================
# DOMAIN RULES
# ============================================================

EXCLUDED_DOMAINS = {
    "example.com",
    "test.com",
    "domain.com",
    "company.com",
    "email.com",
    "placeholder.com",
    "invalid.com",
    "localhost.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "thegaogroup.com",
}

COMMON_DOMAIN_TYPOS = {
    "gmai.com",
    "gmial.com",
    "gamil.com",
    "gmail.co",
    "gmail.con",
    "gmail.cim",
    "gmail.comm",
    "gmail.cpm",
    "outlook.con",
    "outlok.com",
    "hotmail.con",
    "yahoo.con",
    "yaho.com",
}

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "aol.com",
    "live.com",
    "msn.com",
    "protonmail.com",
    "proton.me",
    "zoho.com",
}

DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "tempmail.com",
    "temp-mail.org",
    "yopmail.com",
    "throwawaymail.com",
    "getnada.com",
    "sharklasers.com",
    "trashmail.com",
}

# Common real TLDs plus recruiter/staffing-related modern TLDs.
# Any valid 2-letter country TLD is also accepted.
VALID_TLDS = {
    "com", "net", "org", "edu", "gov", "mil", "int",
    "io", "ai", "co", "us", "uk", "in", "ca", "au", "nz",
    "de", "fr", "nl", "ie", "ch", "se", "no", "dk", "fi",
    "sg", "my", "ae", "sa", "qa", "kw", "om", "za",
    "jp", "kr", "ph", "id", "pk", "bd", "lk", "np",
    "tech", "dev", "cloud", "digital", "agency", "careers",
    "jobs", "consulting", "solutions", "services", "global",
    "group", "team", "studio", "media", "marketing",
    "company", "business", "inc", "llc", "online",
}

COMMON_BAD_TLDS = {
    "con",
    "comm",
    "cpm",
    "cim",
    "vom",
    "coom",
    "come",
    "om",
    "cm",
}


# ============================================================
# ADDRESS RULES
# ============================================================

EXCLUDED_EMAILS = {
    "noreply@linkedin.com",
    "notifications@linkedin.com",
    "security@linkedin.com",
}

BLOCKED_EMAIL_KEYWORDS = {
    "hire-bangladesh",
    "hire-pakistan",
    "hire-india",
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "yourname",
    "your-name",
    "username",
    "firstlast",
    "firstname",
    "lastname",
    "sample",
    "dummy",
    "placeholder",
    "testemail",
}

BLOCKED_LOCAL_PARTS = {
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "webmaster",
    "privacy",
    "legal",
    "abuse",
    "security",
    "notifications",
}

# Generic addresses that usually do not belong to recruiters.
# Recruiter-focused generic inboxes remain allowed below.
LOW_VALUE_GENERIC_LOCAL_PARTS = {
    "support",
    "help",
    "contact",
    "hello",
    "admin",
    "sales",
    "newsletter",
    "billing",
    "accounts",
    "customer",
    "customerservice",
}

RECRUITER_GENERIC_PREFIXES = (
    "hr",
    "career",
    "careers",
    "job",
    "jobs",
    "talent",
    "recruit",
    "recruiter",
    "recruiting",
    "hiring",
    "staffing",
    "resume",
    "resumes",
    "cv",
    "people",
    "humanresources",
)


# ============================================================
# PUBLIC FUNCTIONS
# ============================================================

def extract_emails(text: str) -> List[str]:
    """
    Extract unique, normalized recruiter-safe emails.

    Existing project compatibility:
        extract_emails(text) -> List[str]
    """
    if text is None or not str(text).strip():
        return []

    original_text = str(text)
    normalized_text = _normalize_obfuscated_text(original_text)

    candidates: Set[str] = set()

    for source_text in (original_text, normalized_text):
        for match in EMAIL_PATTERN.findall(source_text):
            cleaned = _clean_email(match)

            if not cleaned:
                continue

            valid, reason = validate_email(cleaned)

            if valid:
                candidates.add(cleaned)
            else:
                logger.debug(
                    "Rejected extracted email %s: %s",
                    cleaned,
                    reason,
                )

    return sorted(candidates)


def extract_emails_batch(texts: List[str]) -> List[str]:
    all_emails: Set[str] = set()

    for text in texts or []:
        all_emails.update(extract_emails(text))

    return sorted(all_emails)


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email syntax and recruiter relevance.

    Returns:
        (True, "ok")
        (False, "reason")
    """
    email = _clean_email(email)

    if not email:
        return False, "empty"

    if len(email) < 6 or len(email) > 254:
        return False, "invalid_length"

    if email in EXCLUDED_EMAILS:
        return False, "excluded_email"

    if not EMAIL_PATTERN.fullmatch(email):
        return False, "invalid_format"

    if email.count("@") != 1:
        return False, "invalid_at_count"

    local, domain = email.rsplit("@", 1)
    local = local.strip(".").lower()
    domain = domain.strip(".").lower()

    if not local or not domain:
        return False, "missing_local_or_domain"

    if len(local) > 64 or len(domain) > 253:
        return False, "invalid_part_length"

    if local.startswith(".") or local.endswith("."):
        return False, "local_dot_boundary"

    if ".." in local or ".." in domain:
        return False, "double_dot"

    if "_" in domain:
        return False, "underscore_in_domain"

    if domain.startswith("-") or domain.endswith("-"):
        return False, "domain_hyphen_boundary"

    if domain in EXCLUDED_DOMAINS:
        return False, "excluded_domain"

    if domain in COMMON_DOMAIN_TYPOS:
        return False, "common_domain_typo"

    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return False, "disposable_domain"

    if any(keyword in email for keyword in BLOCKED_EMAIL_KEYWORDS):
        return False, "blocked_keyword"

    if local in BLOCKED_LOCAL_PARTS:
        return False, "blocked_local_part"

    domain_labels = domain.split(".")

    if len(domain_labels) < 2:
        return False, "missing_tld"

    for label in domain_labels:
        if not label:
            return False, "empty_domain_label"

        if label.startswith("-") or label.endswith("-"):
            return False, "bad_domain_label"

        if not re.fullmatch(r"[a-z0-9\-]+", label):
            return False, "invalid_domain_character"

    tld = domain_labels[-1]

    if tld in COMMON_BAD_TLDS:
        return False, "bad_tld"

    if any(char.isdigit() for char in tld):
        return False, "numeric_tld"

    # Accept known TLDs and normal two-letter country-code TLDs.
    if tld not in VALID_TLDS and len(tld) != 2:
        return False, "unknown_or_suspicious_tld"

    # Blocks LinkedIn text fragments such as:
    # me@keerti.pandey
    # resume@sakshi.aswal
    if _looks_like_person_name_domain(domain):
        return False, "person_name_used_as_domain"

    local_letters = re.sub(r"[^a-z]", "", local)

    if not local_letters:
        return False, "local_without_letters"

    if local in LOW_VALUE_GENERIC_LOCAL_PARTS:
        return False, "non_recruiter_generic_address"

    if _looks_like_placeholder_local(local):
        return False, "placeholder_local"

    if _has_excessive_digits(local):
        return False, "excessive_digits"

    if _has_repeated_junk(local):
        return False, "repeated_junk"

    # Free mailboxes are allowed, but very short or meaningless usernames
    # are rejected.
    if domain in FREE_EMAIL_DOMAINS:
        if len(local) < 5:
            return False, "short_free_mailbox"

        if not _looks_like_recruiter_or_personal_mailbox(local):
            return False, "risky_free_mailbox"

    return True, "ok"


def is_valid_email(email: str) -> bool:
    valid, _ = validate_email(email)
    return valid


# Old private-function compatibility.
def _is_valid_email(email: str) -> bool:
    return is_valid_email(email)


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _normalize_obfuscated_text(text: str) -> str:
    text = str(text or "")

    text = re.sub(
        r"\s*(?:\[|\()\s*at\s*(?:\]|\))\s*",
        "@",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s+\bat\b\s+",
        "@",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*(?:\[|\()\s*dot\s*(?:\]|\))\s*",
        ".",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s+\bdot\b\s+",
        ".",
        text,
        flags=re.IGNORECASE,
    )

    # Common visible spacing around @ and dots.
    text = re.sub(r"\s*@\s*", "@", text)
    text = re.sub(r"\s+\.\s+", ".", text)

    return text


def _clean_email(email: str) -> str:
    email = str(email or "").strip().lower()
    email = email.replace("mailto:", "")
    email = email.replace("\u200b", "")
    email = email.replace("\u200c", "")
    email = email.replace("\u200d", "")
    email = email.replace("\ufeff", "")

    email = email.lstrip("([{<'\"`")
    email = email.rstrip(".,;:!?)>]}'\"`")

    return email.strip()


def _looks_like_person_name_domain(domain: str) -> bool:
    """
    LinkedIn card extraction sometimes joins words around an email:

        "email me @ Keerti.Pandey"
        -> me@keerti.pandey

    A surname-looking TLD is rejected by the TLD rules. This helper catches
    additional person-name patterns.
    """
    labels = domain.lower().split(".")

    if len(labels) != 2:
        return False

    first, second = labels

    if second in VALID_TLDS or len(second) == 2:
        return False

    if (
        first.isalpha()
        and second.isalpha()
        and 3 <= len(first) <= 20
        and 3 <= len(second) <= 20
    ):
        return True

    return False


def _looks_like_placeholder_local(local: str) -> bool:
    low = local.lower()

    fragments = {
        "example",
        "sample",
        "dummy",
        "placeholder",
        "yourname",
        "username",
        "firstname",
        "lastname",
        "firstlast",
        "testmail",
        "testemail",
        "abcdef",
        "abc123",
        "xyz123",
    }

    return any(fragment in low for fragment in fragments)


def _has_excessive_digits(local: str) -> bool:
    digits = sum(char.isdigit() for char in local)

    if digits == 0:
        return False

    if digits >= 7:
        return True

    # Reject mailboxes mostly made of digits.
    if digits / max(len(local), 1) > 0.55:
        return True

    return False


def _has_repeated_junk(local: str) -> bool:
    # Examples: aaaaaaaa@gmail.com, testtesttest@gmail.com
    if re.search(r"(.)\1{5,}", local):
        return True

    compact = re.sub(r"[^a-z0-9]", "", local)

    if len(compact) >= 12:
        half = len(compact) // 2
        if compact[:half] == compact[half:half * 2]:
            return True

    return False


def _looks_like_recruiter_or_personal_mailbox(local: str) -> bool:
    low = local.lower()

    if low.startswith(RECRUITER_GENERIC_PREFIXES):
        return True

    # Normal personal Gmail/Outlook mailbox:
    # at least 6 characters, at least 4 letters, no excessive digits.
    letter_count = sum(char.isalpha() for char in low)
    digit_count = sum(char.isdigit() for char in low)

    if len(low) < 6:
        return False

    if letter_count < 4:
        return False

    if digit_count > 4:
        return False

    return True