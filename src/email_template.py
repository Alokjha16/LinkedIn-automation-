"""
email_template.py

Professional recruiter outreach email generator.

Flow:

Greeting
↓
Short introduction
↓
Candidate Overview
↓
Profile fit
↓
Resume CTA
↓
Thank you
↓
Best regards
↓
Requirement Details
↓
LinkedIn Post
"""

import html
import json
import random
import re
from typing import Any, Dict, Tuple

from config import (
    CANDIDATE_DATA_FILE,
    SENDER_NAME,
)


# ============================================================
# CONSTANTS
# ============================================================

MISSING_VALUES = {
    "",
    "none",
    "nan",
    "n/a",
    "na",
    "null",
    "not available",
    "not avail",
    "not mentioned",
    "unknown",
}


INVALID_RECRUITER_NAMES = {
    "linkedin recruiter",
    "recruiter",
    "linkedin member",

    "talent acquisition",
    "talent acquisition manager",
    "talent acquisition specialist",

    "human resources",
    "human resource",

    "hr",

    "hiring manager",
    "hiring",

    "senior director",
    "director",
    "manager",
    "admin",

    # Important: prevents "Hello Now"
    "now",
    "hello",
    "hi",
    "hey",

    "edited",
    "today",
    "yesterday",
    "tomorrow",

    "unknown",
    "undefined",
}


RECRUITER_TITLE_WORDS = {
    "recruiter",
    "recruitment",
    "talent",
    "acquisition",
    "specialist",
    "manager",
    "director",
    "head",
    "lead",
    "partner",
    "consultant",
    "human",
    "resources",
    "hr",
    "senior",
    "executive",
    "officer",
    "founder",
    "ceo",
    "president",
    "staffing",
    "hiring",
}


ROLE_NOISE_PATTERNS = [

    r"\burgently\s+hiring\b",
    r"\bnow\s+hiring\b",
    r"\bwe're\s+hiring\b",
    r"\bwe\s+are\s+hiring\b",

    r"\bhiring\b",
    r"\bopenings?\b",
    r"\bjob\s+opening\b",

    r"\bimmediate\s+requirement\b",

    r"\brequirements?\b",
    r"\brequired\b",
    r"\bneeded\b",
    r"\bneed\b",

    r"\bapply\s+now\b",

    r"\busa\b",
    r"\bu\.?s\.?a?\.?\b",
    r"\bunited\s+states\b",

    r"\bremote\b",
    r"\bhybrid\b",
    r"\bonsite\b",
    r"\bon[-\s]?site\b",
]


# ============================================================
# LOAD CANDIDATE
# ============================================================

def load_candidate_data() -> Dict[str, Any]:

    try:

        with open(
            CANDIDATE_DATA_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        return data or {}

    except Exception:

        return {}


# ============================================================
# CLEANING
# ============================================================

def clean_text(value: Any) -> str:

    if value is None:
        return ""

    text = str(value)

    text = (
        text
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def clean_multiline_text(value: Any) -> str:

    if value is None:
        return ""

    text = str(value)

    text = (
        text
        .replace("\r", "\n")
        .replace("\t", " ")
    )

    # LinkedIn UI noise.
    noise_patterns = [

        r"^.*?You can still react or share it\.\s*",

        r"\bSee more\b",
        r"\bShow more\b",

    ]

    for pattern in noise_patterns:

        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

    lines = []

    for raw_line in text.splitlines():

        line = re.sub(
            r"\s+",
            " ",
            raw_line
        ).strip()

        if not line:
            continue

        if line.lower() in {
            "like",
            "comment",
            "repost",
            "send",
            "share",
            "follow",
            "connect",
        }:
            continue

        lines.append(line)

    text = "\n".join(lines)

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# VALUE HELPERS
# ============================================================

def get_value(
    obj: Any,
    *keys: str,
    default: str = ""
) -> str:

    if obj is None:
        return default

    for key in keys:

        try:

            value = obj.get(
                key,
                ""
            )

        except Exception:

            continue

        text = clean_text(value)

        if (
            text
            and text.lower()
            not in MISSING_VALUES
        ):
            return text

    return default


# ============================================================
# ROLE
# ============================================================

def clean_job_role(
    role: Any,
    candidate: Dict[str, Any] | None = None
) -> str:

    candidate = candidate or {}

    title = clean_text(role)

    if not title:

        title = clean_text(
            candidate.get(
                "title",
                "Professional"
            )
        )

    for pattern in ROLE_NOISE_PATTERNS:

        title = re.sub(
            pattern,
            " ",
            title,
            flags=re.IGNORECASE
        )

    title = re.sub(
        r"\s*[-|:/]+\s*$",
        "",
        title
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    ).strip(
        " -|:/,."
    )

    if not title:

        title = (
            clean_text(
                candidate.get(
                    "title",
                    "Professional"
                )
            )
            or "Professional"
        )

    return title


# ============================================================
# RECRUITER NAME VALIDATION
# ============================================================

def is_valid_person_name(
    value: Any
) -> bool:

    name = clean_text(value)

    lower_name = (
        name
        .lower()
        .strip(" ,.-")
    )

    if not name:
        return False

    if lower_name in MISSING_VALUES:
        return False

    if lower_name in INVALID_RECRUITER_NAMES:
        return False

    if any(
        token in lower_name.split()
        for token in [
            "now",
            "hiring",
            "recruiter",
            "recruitment",
            "talent",
            "hr",
            "manager",
        ]
    ):
        return False

    if any(
        char.isdigit()
        for char in name
    ):
        return False

    if "@" in name:
        return False

    if "http" in lower_name:
        return False

    if "linkedin" in lower_name:
        return False

    if any(
        token in lower_name
        for token in [
            "ago",
            "hour",
            "minute",
            "followers",
            "connections",
            "edited",
        ]
    ):
        return False

    words = [
        word
        for word in re.split(
            r"\s+",
            name
        )
        if word
    ]

    if not 1 <= len(words) <= 5:
        return False

    alpha_words = [
        re.sub(
            r"[^A-Za-z'-]",
            "",
            word
        )
        for word in words
    ]

    if not all(
        word and re.search(
            r"[A-Za-z]",
            word
        )
        for word in alpha_words
    ):
        return False

    title_hits = sum(
        1
        for word in words
        if word.lower().strip(".,")
        in RECRUITER_TITLE_WORDS
    )

    if title_hits >= max(
        1,
        len(words) - 1
    ):
        return False

    return True


# ============================================================
# INFER RECRUITER NAME
# ============================================================

def infer_recruiter_name_from_post(
    post_text: Any
) -> str:

    text = str(
        post_text or ""
    ).replace(
        "\r",
        "\n"
    )

    first_chunk = re.split(
        r"[•\n]",
        text,
        maxsplit=1
    )[0]

    first_chunk = re.sub(
        r"\b\d+\s*(?:m|min|mins|h|hr|hrs|d|day|days|w|week|weeks)\b",
        "",
        first_chunk,
        flags=re.I
    )

    first_chunk = re.sub(
        r"\b\d+(?:st|nd|rd|th)\+?\b",
        "",
        first_chunk,
        flags=re.I
    )

    first_chunk = clean_text(
        first_chunk
    )

    if is_valid_person_name(
        first_chunk
    ):
        return first_chunk

    return ""


def resolve_recruiter_name(
    lead: Any
) -> str:

    recruiter_name = get_value(
        lead,
        "recruiter_name",
        "contact_name",
        "name",
        default=""
    )

    if is_valid_person_name(
        recruiter_name
    ):
        return recruiter_name

    post_text = get_value(
        lead,
        "full_post_text",
        "post_text",
        "post_content",
        "post_snippet",
        default=""
    )

    inferred = (
        infer_recruiter_name_from_post(
            post_text
        )
    )

    if inferred:
        return inferred

    return ""


# ============================================================
# REQUIREMENT SNAPSHOT
# ============================================================

def create_requirement_snapshot(
    jd_text: Any,
    max_len: int | None = None
) -> str:

    text = clean_multiline_text(
        jd_text
    )

    if not text:

        return (
            "The complete requirement details "
            "were not available in the LinkedIn post."
        )

    if (
        max_len
        and max_len > 0
        and len(text) > max_len
    ):

        return (
            text[:max_len]
            .rsplit(" ", 1)[0]
            .strip()
            + "..."
        )

    return text


# ============================================================
# NORMALIZE INPUTS
# ============================================================

def normalize_inputs(
    lead: Any = None,
    candidate: Dict[str, Any] | None = None
) -> Tuple[
    Any,
    Dict[str, Any],
    str,
    str,
    str,
    str
]:

    candidate = (
        candidate
        or load_candidate_data()
    )

    recruiter_name = (
        resolve_recruiter_name(
            lead
        )
    )

    raw_role = get_value(
        lead,
        "job_role",
        "job_title",
        "role",
        "keyword",
        default=""
    )

    job_role = clean_job_role(
        raw_role,
        candidate
    )

    jd_text = get_value(
        lead,
        "full_post_text",
        "post_text",
        "post_content",
        "content",
        "job_description",
        "description",
        "post_snippet",
        default=""
    )

    post_url = get_value(
        lead,
        "post_url",
        default=""
    )

    return (
        lead,
        candidate,
        recruiter_name,
        job_role,
        jd_text,
        post_url
    )


# ============================================================
# PROFESSIONAL SUBJECT
# ============================================================

def generate_subject(
    lead: Any = None,
    candidate: Dict[str, Any] | None = None,
    job_role: str = ""
) -> str:

    (
        _,
        candidate,
        _,
        detected_role,
        _,
        _
    ) = normalize_inputs(
        lead,
        candidate
    )

    candidate_name = clean_text(
        candidate.get(
            "full_name"
        )
        or candidate.get(
            "name"
        )
        or "Candidate"
    )

    title = clean_job_role(
        job_role
        or detected_role,
        candidate
    )

    # Short, professional and recruiter-readable.
    patterns = [

        f"{candidate_name} | {title} | Candidate Profile",

        f"{title} Candidate | {candidate_name}",

        f"{candidate_name} – {title} Opportunity",

        f"Candidate Submission | {title} | {candidate_name}",

        f"{candidate_name} | Qualified Candidate for {title}",

    ]

    return random.choice(
        patterns
    )


# ============================================================
# CANDIDATE DETAILS
# ============================================================

def build_candidate_details(
    candidate: Dict[str, Any]
) -> list[tuple[str, str]]:

    details = [

        (
            "Name",
            clean_text(
                candidate.get(
                    "full_name"
                )
                or candidate.get(
                    "name"
                )
            )
        ),

        (
            "Current Location",
            clean_text(
                candidate.get(
                    "current_location"
                )
                or candidate.get(
                    "location"
                )
            )
        ),

        (
            "Preferred Location",
            clean_text(
                candidate.get(
                    "preferred_location"
                )
            )
        ),

        (
            "Open to Relocate",
            clean_text(
                candidate.get(
                    "open_to_relocate"
                )
            )
        ),

        (
            "Work Authorization",
            clean_text(
                candidate.get(
                    "work_authorization"
                )
            )
        ),

        (
            "Experience",
            clean_text(
                candidate.get(
                    "total_experience"
                )
                or candidate.get(
                    "experience"
                )
            )
        ),

        (
            "Availability",
            clean_text(
                candidate.get(
                    "availability"
                )
            )
        ),

        (
            "Email",
            clean_text(
                candidate.get(
                    "email"
                )
            )
        ),

        (
            "Phone",
            clean_text(
                candidate.get(
                    "phone"
                )
            )
        ),

        (
            "LinkedIn",
            clean_text(
                candidate.get(
                    "linkedin"
                )
            )
        ),
    ]

    return [
        (
            label,
            value
        )
        for label, value in details
        if (
            value
            and value.lower()
            not in MISSING_VALUES
        )
    ]


# ============================================================
# PLAIN TEXT EMAIL
# ============================================================

def generate_email_body(
    lead: Any = None,
    candidate: Dict[str, Any] | None = None,
    job_role: str = "",
    jd_text: str = "",
    post_url: str = ""
) -> str:

    (
        _,
        candidate,
        recruiter_name,
        detected_role,
        detected_jd,
        detected_post_url
    ) = normalize_inputs(
        lead,
        candidate
    )

    title = clean_job_role(
        job_role or detected_role,
        candidate
    )

    jd_text = (
        jd_text
        or detected_jd
    )

    post_url = (
        post_url
        or detected_post_url
    )

    candidate_name = clean_text(
        candidate.get(
            "full_name"
        )
        or candidate.get(
            "name"
        )
        or "the candidate"
    )

    # Never use "Hello Now", "Hello Recruiter", etc.
    if recruiter_name:

        greeting = (
            f"Hello {recruiter_name},"
        )

    else:

        greeting = "Hello,"

    details_text = "\n".join(
        f"{label}: {value}"
        for label, value
        in build_candidate_details(
            candidate
        )
    )

    requirement_text = (
        create_requirement_snapshot(
            jd_text
        )
    )

    post_line = ""

    if (
        post_url
        and "linkedin.com"
        in post_url.lower()
    ):

        post_line = (
            f"\nLinkedIn Post: {post_url}"
        )

    body = f"""{greeting}

I hope you are doing well.

I came across your opening for {title} and wanted to share {candidate_name}'s profile for your consideration.

Candidate Overview

{details_text}

I have attached {candidate_name}'s resume for your review. Based on the candidate's background and the nature of this opening, I would appreciate your consideration for this opportunity or any closely related role within your team.

Please let me know if the profile aligns with your current requirement or if you would like any additional information.

Thank you for your time and consideration.

Best regards,
{SENDER_NAME}

────────────────────────────────────────

Requirement Details

{requirement_text}
{post_line}
"""

    return body.strip()


# ============================================================
# HTML EMAIL
# ============================================================

def generate_html_email_body(
    lead: Any = None,
    candidate: Dict[str, Any] | None = None,
    job_role: str = "",
    jd_text: str = "",
    post_url: str = ""
) -> str:

    (
        _,
        candidate,
        recruiter_name,
        detected_role,
        detected_jd,
        detected_post_url
    ) = normalize_inputs(
        lead,
        candidate
    )

    title = clean_job_role(
        job_role or detected_role,
        candidate
    )

    jd_text = (
        jd_text
        or detected_jd
    )

    post_url = (
        post_url
        or detected_post_url
    )

    candidate_name = clean_text(
        candidate.get(
            "full_name"
        )
        or candidate.get(
            "name"
        )
        or "the candidate"
    )

    if recruiter_name:

        greeting = (
            f"Hello {html.escape(recruiter_name)},"
        )

    else:

        greeting = "Hello,"

    safe_title = html.escape(
        title
    )

    safe_candidate_name = html.escape(
        candidate_name
    )

    details_rows = ""

    for label, value in build_candidate_details(
        candidate
    ):

        safe_label = html.escape(
            label
        )

        safe_value = html.escape(
            value
        )

        details_rows += (
            "<tr>"
            f"<td style='padding:4px 18px 4px 0;"
            f"font-weight:600;vertical-align:top;'>"
            f"{safe_label}:</td>"
            f"<td style='padding:4px 0;"
            f"vertical-align:top;'>"
            f"{safe_value}</td>"
            "</tr>"
        )

    requirement_text = (
        create_requirement_snapshot(
            jd_text
        )
    )

    requirement_html = (
        html.escape(
            requirement_text
        )
        .replace(
            "\n",
            "<br>"
        )
    )

    post_html = ""

    if (
        post_url
        and "linkedin.com"
        in post_url.lower()
    ):

        safe_url = html.escape(
            post_url,
            quote=True
        )

        post_html = (
            "<p style='margin:12px 0 0;'>"
            "<strong>LinkedIn Post:</strong> "
            f"<a href='{safe_url}'>{safe_url}</a>"
            "</p>"
        )

    return f"""
<html>
<head>
<meta charset="UTF-8">
</head>

<body style="
font-family:Arial,Helvetica,sans-serif;
font-size:14px;
color:#222;
line-height:1.65;
margin:0;
padding:0;
">

<p>{greeting}</p>

<p>
I hope you are doing well.
</p>

<p>
I came across your opening for
<strong>{safe_title}</strong>
and wanted to share
<strong>{safe_candidate_name}</strong>'s
profile for your consideration.
</p>

<p style="margin-bottom:7px;">
<strong>Candidate Overview</strong>
</p>

<table
cellpadding="0"
cellspacing="0"
border="0"
style="border-collapse:collapse;margin-bottom:18px;"
>
{details_rows}
</table>

<p>
I have attached
<strong>{safe_candidate_name}</strong>'s
resume for your review. Based on the candidate's
background and the nature of this opening, I would
appreciate your consideration for this opportunity
or any closely related role within your team.
</p>

<p>
Please let me know if the profile aligns with your
current requirement or if you would like any
additional information.
</p>

<p>
Thank you for your time and consideration.
</p>

<p>
Best regards,<br>
<strong>{html.escape(SENDER_NAME)}</strong>
</p>

<hr style="
border:none;
border-top:1px solid #dddddd;
margin:22px 0;
">

<p style="margin-bottom:7px;">
<strong>Requirement Details</strong>
</p>

<div style="
background:#f8f9fa;
border-left:3px solid #555;
padding:13px 15px;
margin-bottom:12px;
font-size:13px;
line-height:1.6;
">
{requirement_html}
</div>

{post_html}

</body>
</html>
""".strip()


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

def generate_email_html_body(
    lead: Any = None,
    candidate: Dict[str, Any] | None = None,
    job_role: str = "",
    jd_text: str = "",
    post_url: str = ""
) -> str:

    return generate_html_email_body(
        lead=lead,
        candidate=candidate,
        job_role=job_role,
        jd_text=jd_text,
        post_url=post_url
    )