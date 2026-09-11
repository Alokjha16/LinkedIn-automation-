#!/usr/bin/env python3

import argparse
import logging
import random
import re
import sys
import time
import socket
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("automation.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

from config import (
    DRY_RUN,
    DEFAULT_SEARCH_KEYWORDS,
    DEFAULT_RESUME_PATH,
    EMAIL_SEND_DELAY,
    MAX_EMAILS_PER_SESSION,
    LEADS_CSV,
    CURRENT_CANDIDATE,
    SENDER_EMAIL,
    SENDER_NAME,
)

try:
    from config import TRACKING_EMAIL
except Exception:
    TRACKING_EMAIL = "kim@jpitstaffing.com"

from src.linkedin_scraper import scrape_linkedin_posts
from src.gmail_service import authenticate_gmail, send_or_draft
from src.csv_manager import save_leads, get_unsent_leads, log_sent_email, preview_leads
from src.email_template import load_candidate_data, generate_subject, generate_email_body, generate_email_html_body
from src.resume_customizer import customize_resume


MISSING_VALUES = ["", "0", "none", "nan", "n/a", "null", "not available", "not avail", "not mentioned"]




# =========================
# PRE-SEND EMAIL VALIDATION
# =========================
# This prevents most "Address not found" bounces by skipping
# malformed, placeholder, dead-domain, and risky emails before Gmail sends.

EMAIL_REGEX_STRICT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._%+\-]{0,63}@[A-Za-z0-9][A-Za-z0-9.\-]{1,253}\.[A-Za-z]{2,24}$"
)

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "aol.com", "protonmail.com", "live.com", "msn.com"
}

BLOCKED_EMAIL_DOMAINS = {
    "example.com", "test.com", "domain.com", "company.com", "email.com",
    "linkedin.com", "mail.com", "gmai.com", "gmial.com", "gmail.co",
    "gmail.con", "outlook.con", "yahoo.con"
}

BLOCKED_LOCAL_PARTS = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "support", "help", "info", "admin", "webmaster",
    "privacy", "legal", "sales", "marketing", "newsletter"
}

COMMON_BAD_TLDS = {
    "con", "comm", "cpm", "vom", "cim", "om", "cm", "coom", "come"
}

DOMAIN_CACHE = {}


def normalize_email_candidate(email):
    email = str(email or "").strip().lower()
    email = email.replace("mailto:", "")
    email = email.strip(" ,;:()[]{}<>\"'")
    email = re.sub(r"^[^a-z0-9]+", "", email)
    email = re.sub(r"[^a-z0-9]+$", "", email)
    email = email.replace("..", ".")
    email = email.replace("@.", "@")
    email = email.replace(".@", "@")
    return email


def domain_has_dns(domain):
    domain = str(domain or "").strip().lower()

    if domain in DOMAIN_CACHE:
        return DOMAIN_CACHE[domain]

    try:
        # If domain cannot resolve at all, it is very likely to bounce.
        socket.getaddrinfo(domain, 25)
        DOMAIN_CACHE[domain] = True
        return True
    except Exception:
        try:
            socket.getaddrinfo(domain, 443)
            DOMAIN_CACHE[domain] = True
            return True
        except Exception:
            DOMAIN_CACHE[domain] = False
            return False


def is_valid_recipient_email(email, check_domain=True):
    email = normalize_email_candidate(email)

    if not email or "@" not in email:
        return False, "empty_or_missing_at"

    if len(email) < 6 or len(email) > 254:
        return False, "bad_length"

    if not EMAIL_REGEX_STRICT.fullmatch(email):
        return False, "bad_format"

    local, domain = email.rsplit("@", 1)
    local = local.strip(".")
    domain = domain.strip(".").lower()

    if not local or not domain:
        return False, "bad_parts"

    if domain in BLOCKED_EMAIL_DOMAINS:
        return False, "blocked_domain"

    if domain.startswith("-") or domain.endswith("-") or ".." in domain or "_" in domain:
        return False, "bad_domain"

    tld = domain.split(".")[-1]
    if tld in COMMON_BAD_TLDS:
        return False, "bad_tld"

    local_alpha = re.sub(r"[^a-z]", "", local.lower())
    if local_alpha in BLOCKED_LOCAL_PARTS:
        return False, "blocked_local"

    placeholder_fragments = [
        "example", "yourname", "username", "firstlast", "firstname",
        "lastname", "sample", "dummy", "testemail", "null"
    ]
    if any(fragment in local.lower() for fragment in placeholder_fragments):
        return False, "placeholder_email"

    # Free Gmail/Yahoo recruiter emails are allowed only if they look recruiter-related.
    if domain in FREE_EMAIL_DOMAINS:
        allowed_prefixes = (
            "hr", "recruit", "recruiter", "recruiting", "talent",
            "careers", "jobs", "staffing", "hiring", "resume", "resumes"
        )
        if not local.lower().startswith(allowed_prefixes) and len(local) < 8:
            return False, "weak_free_email"

    if check_domain and domain not in FREE_EMAIL_DOMAINS:
        if not domain_has_dns(domain):
            return False, "domain_not_found"

    return True, "ok"


def split_and_validate_emails(raw_emails):
    cleaned = []
    seen = set()

    for raw in str(raw_emails or "").split(","):
        email = normalize_email_candidate(raw)
        if not email or email in seen:
            continue

        ok, reason = is_valid_recipient_email(email, check_domain=True)
        if not ok:
            print(f"  ⚠️ Skipping bounce-risk email: {email} ({reason})")
            continue

        seen.add(email)
        cleaned.append(email)

    return cleaned


def clean_value(value, default=""):
    if value is None:
        return default
    value = str(value).strip()
    if value.lower() in MISSING_VALUES:
        return default
    return value


def get_value(data, keys, default=""):
    for key in keys:
        try:
            value = clean_value(data.get(key, ""))
            if value:
                return value
        except Exception:
            pass
    return default


def load_current_candidate():
    try:
        candidate = load_candidate_data()
        if candidate:
            return candidate
    except Exception as e:
        print(f"\n⚠️ Could not load candidate_data.json: {e}")

    print("\nℹ️ Using CURRENT_CANDIDATE from config.py")
    return CURRENT_CANDIDATE


def get_post_text_from_lead(lead):
    cols = [
        "full_post_text",
        "post_text",
        "post_content",
        "content",
        "post_snippet",
        "description",
        "job_description",
        "text",
    ]

    for col in cols:
        value = get_value(lead, [col], "")
        if value:
            return value

    return " ".join([
        get_value(lead, ["job_role", "job_title", "role"], ""),
        get_value(lead, ["location"], ""),
        get_value(lead, ["emails"], ""),
    ]).strip()


def is_current_candidate_marketing():
    try:
        candidate = load_current_candidate()
        title = str(candidate.get("title", "")).lower()
        return any(x in title for x in ["marketing", "seo", "ppc", "growth", "performance", "digital"])
    except Exception:
        return True


def normalize_role_category(job_role, post_text=""):
    """Resume cache category. For Siddhu, never create cyber resume categories."""
    text = f"{job_role} {post_text}".lower()

    if is_current_candidate_marketing():
        if any(x in text for x in ["seo", "search engine optimization", "keyword research", "organic traffic"]):
            return "digital_marketing_seo"
        if any(x in text for x in ["ppc", "google ads", "paid search", "sem", "cpc", "ctr"]):
            return "digital_marketing_ppc"
        if any(x in text for x in ["email marketing", "mailchimp", "hubspot", "marketing automation"]):
            return "digital_marketing_email"
        if any(x in text for x in ["social media", "meta ads", "facebook ads", "linkedin ads"]):
            return "digital_marketing_social"
        return "digital_marketing_general"

    if any(x in text for x in ["business analyst", "requirements", "brd", "frd", "uat"]):
        return "business_analyst"
    if any(x in text for x in ["scrum master", "agile", "sprint planning"]):
        return "scrum_master"

    safe = re.sub(r"[^a-z0-9]+", "_", text[:50]).strip("_")
    return safe or "general"

def is_non_us_or_bad_location(text):
    text = f" {str(text or '').lower()} "

    blocked_locations = [
        " india", " delhi", " pune", " chennai", " hyderabad", " bangalore", " bengaluru", " mumbai", " noida", " gurgaon",
        " canada", " malaysia", " pakistan", " bangladesh", " singapore", " philippines", " australia",
        " europe", " uk ", " united kingdom", " germany", " france", " netherlands", " dubai", " uae", " qatar", " saudi"
    ]

    if any(loc in text for loc in blocked_locations):
        # Allow only when it is clearly a USA-only remote requirement.
        if not any(x in text for x in [" usa only", " us only", " united states only", " remote usa", " remote us"]):
            return True

    return False


def is_jd_relevant_to_role(post_text, target_role):
    post_lower = str(post_text or "").lower()
    role_lower = str(target_role or "").lower()

    domain_keywords = {
        "seo": ["seo", "search engine optimization", "organic traffic", "on-page", "off-page", "screaming frog", "semrush", "ahrefs", "google search console"],
        "ppc": ["ppc", "google ads", "paid search", "paid social", "adwords", "sem", "click-through", "ctr", "cpc"],
        "marketing": ["marketing", "marketer", "campaign", "lead generation", "hubspot", "mailchimp", "social media", "content strategy"],
        "soc": ["soc", "security operations center", "incident response", "siem", "splunk", "sentinel", "qradar", "wazuh", "security monitoring", "blue team"],
        "cyber": ["cybersecurity", "cyber security", "information security", "it security", "vulnerability", "penetration", "firewall", "ids/ips"],
        "iam": ["iam", "identity access", "active directory", "okta", "cyberark", "sailpoint", "provisioning"],
        "grc": ["grc", "governance", "compliance", "risk", "nist", "iso 27001", "soc2", "hipaa", "pci"]
    }

    matched_domains = []
    for domain, terms in domain_keywords.items():
        if domain in role_lower or any(t in role_lower for t in terms if len(t) > 3):
            matched_domains.append((domain, terms))

    if not matched_domains:
        role_words = [w for w in re.split(r"[^a-zA-Z0-9]+", role_lower) if len(w) > 3 and w not in ["hiring", "need", "requirement", "requirements", "contract", "remote", "onsite", "hybrid", "opportunity", "opening", "position", "analyst", "specialist", "engineer"]]
        if not role_words:
            return True
        return any(w in post_lower for w in role_words)

    for domain, terms in matched_domains:
        if domain in post_lower or any(t in post_lower for t in terms):
            return True

    return False


def score_lead(lead):
    job_role = get_value(lead, ["job_role", "job_title", "role", "keyword"], "")
    post_text = get_post_text_from_lead(lead)

    text = " ".join([
        get_value(lead, ["full_post_text"], ""),
        get_value(lead, ["post_snippet"], ""),
        job_role,
        get_value(lead, ["location"], ""),
        get_value(lead, ["emails"], ""),
    ]).lower()

    if is_non_us_or_bad_location(text):
        return -100

    if job_role and not is_jd_relevant_to_role(post_text, job_role):
        return -100

    score = 0

    marketing_words = [
        "digital marketing", "digital marketer", "marketing specialist", "marketing executive", "marketing coordinator",
        "seo", "seo specialist", "seo executive", "seo analyst", "search engine optimization", "keyword research",
        "on-page", "off-page", "technical seo", "google search console", "organic traffic",
        "ppc", "google ads", "adwords", "paid search", "sem", "performance marketing", "growth marketing",
        "email marketing", "mailchimp", "hubspot", "marketing automation", "crm",
        "social media", "meta ads", "facebook ads", "linkedin ads", "content marketing", "content strategy",
        "lead generation", "demand generation", "landing page", "conversion rate", "campaign management", "campaign optimization",
        "google analytics", "ga4", "campaign reporting", "competitor analysis"
    ]

    hiring_words = [
        "hiring", "urgent", "immediate", "send resume", "share resume", "email resume",
        "looking for", "requirement", "requirements", "opening", "role", "position", "opportunity",
        "contract", "full time", "remote", "hybrid", "onsite"
    ]

    bad_words = [
        "bench sales", "hotlist", "hot list", "vendor list", "available candidates", "available consultants",
        "training and placement", "placement support", "job support", "proxy interview", "fake profile",
        "we provide consultants", "pay after placement"
    ]

    cyber_words = [
        "soc analyst", "security monitoring", "siem", "splunk", "wazuh", "iam", "incident response",
        "threat intelligence", "digital forensics", "dfir", "cybersecurity", "security analyst", "vulnerability"
    ]

    marketing_hits = sum(1 for word in marketing_words if word in text)
    hiring_hits = sum(1 for word in hiring_words if word in text)

    # Siddhu is Digital Marketing. Do not send to SOC/IAM/DFIR/cyber roles.
    if is_current_candidate_marketing():
        if marketing_hits == 0:
            return -100
        if any(word in text for word in cyber_words) and marketing_hits < 2:
            return -80

    for word in marketing_words:
        if word in text:
            score += 6

    for word in hiring_words:
        if word in text:
            score += 2

    for word in bad_words:
        if word in text:
            score -= 25

    if is_non_us_or_bad_location(text):
        score -= 60

    if "@" in text:
        score += 8

    if any(x in text for x in ["united states", "usa", "remote usa", "remote us", "new york", "ny", "new jersey", "nj", "california", "texas"]):
        score += 6

    # Avoid generic global spam posts unless clearly marketing-related.
    if "multiple global job openings" in text and marketing_hits < 2:
        score -= 25

    return max(0, score)

def filter_and_rank_leads(unsent_leads, min_score=8):
    if unsent_leads.empty:
        return unsent_leads

    leads = unsent_leads.copy()
    leads["lead_score"] = leads.apply(score_lead, axis=1)
    leads = leads[leads["lead_score"] >= min_score]
    leads = leads.sort_values("lead_score", ascending=False)

    return leads


def send_or_draft_safe(**kwargs):
    try:
        return send_or_draft(**kwargs, bcc=TRACKING_EMAIL)
    except TypeError:
        return send_or_draft(**kwargs)


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║      🔗 LinkedIn Job Post Email Automation                   ║
║      📧 Gmail API + Resume Customization                    ║
║      ⚡ Speed + Lead Scoring Optimized                      ║
║                                                              ║
║      Author: Alok Jha                                        ║
║      Version: 2.0.0 Bounce-Safe Email Validation                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def parse_arguments():
    parser = argparse.ArgumentParser(description="LinkedIn Recruiter Email Automation")
    parser.add_argument("--send", action="store_true", default=False)
    parser.add_argument("--skip-scrape", action="store_true", default=False)
    parser.add_argument("--keywords", nargs="+", default=None)
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument("--max-emails", type=int, default=MAX_EMAILS_PER_SESSION)
    parser.add_argument("--min-score", type=int, default=8)
    return parser.parse_args()


def step_scrape(keywords):
    print("\n" + "=" * 60)
    print("  STEP 1: SCRAPING LINKEDIN POSTS")
    print("=" * 60)

    print(f"\nKeywords to search: {keywords}")
    leads = scrape_linkedin_posts(keywords=keywords)

    if leads:
        save_leads(leads)
        print(f"\n✅ Scraping complete! Found {len(leads)} leads with email addresses.")
    else:
        print("\n⚠️ No leads with email addresses found.")

    return leads


def step_preview_and_confirm(min_score):
    print("\n" + "=" * 60)
    print("  STEP 2: PREVIEW + LEAD SCORING")
    print("=" * 60)

    unsent_leads = get_unsent_leads()

    if unsent_leads.empty:
        print("\n📭 No unsent leads found.")
        return None

    ranked_leads = filter_and_rank_leads(unsent_leads, min_score=min_score)

    if ranked_leads.empty:
        print(f"\n📭 No high-quality leads found after scoring. Min score: {min_score}")
        return None

    print(f"\n✅ Qualified leads after scoring: {len(ranked_leads)}")
    preview_leads(ranked_leads)

    print("\n✅ Auto mode enabled. Proceeding to Email...")
    return ranked_leads


def step_send_emails(unsent_leads, dry_run, fallback_resume_path, max_emails):
    mode_label = "DRAFTING" if dry_run else "SENDING"
    print("\n" + "=" * 60)
    print(f"  STEP 3: {mode_label} EMAILS")
    print("=" * 60)

    candidate = load_current_candidate()

    client_email = get_value(candidate, ["email"], "supaysid@gmail.com")
    candidate_name = get_value(candidate, ["name", "full_name"], "Siddhu Kolamala")

    print("\n👤 Current Candidate:")
    print(f"   Name: {candidate_name}")
    print(f"   Email: {client_email}")
    print(f"   Phone: {get_value(candidate, ['phone', 'mobile'], '+1 973-687-9494')}")
    print(f"   Availability: {get_value(candidate, ['availability'], 'Immediate')}")

    print("\n📧 Email Routing:")
    print("   From: Gmail authenticated sender")
    print("   To: Recruiter")
    print(f"   Cc: {client_email}")
    print(f"   Bcc: {TRACKING_EMAIL}")

    print("\n🔐 Authenticating Gmail API...")

    try:
        gmail_service = authenticate_gmail()
    except Exception as e:
        print(f"\n❌ Gmail authentication failed: {e}")
        return

    resume_cache = {}

    sent_count = 0
    failed_count = 0

    for lead_index, (_, lead) in enumerate(unsent_leads.iterrows(), start=1):
        if sent_count >= max_emails:
            print(f"\n⚠️ Reached maximum emails per session ({max_emails}).")
            break

        emails = split_and_validate_emails(lead.get("emails", ""))
        if not emails:
            print(f"\n⚠️ Lead {lead_index}: No valid recipient emails after validation. Skipping.")
            continue

        recruiter_name = get_value(lead, ["recruiter_name", "name", "contact_name"], "")
        job_role = get_value(lead, ["job_role", "job_title", "role", "keyword"], get_value(candidate, ["title"], "Digital Marketing Specialist"))
        post_text = get_post_text_from_lead(lead)
        role_category = normalize_role_category(job_role, post_text)

        if role_category in resume_cache:
            attach_path = resume_cache[role_category]
            print(f"\n♻️ Reusing cached resume for role category: {role_category}")
        else:
            try:
                custom_resume_path = Path(customize_resume(post_text, lead_index))
                attach_path = custom_resume_path
                resume_cache[role_category] = attach_path
                print(f"\n📄 Custom resume created for {role_category}: {attach_path}")
            except Exception as e:
                print(f"\n⚠️ Custom resume failed for lead {lead_index}: {e}")
                attach_path = fallback_resume_path if fallback_resume_path.exists() else None

        for email_addr in emails:
            if sent_count >= max_emails:
                break

            if email_addr.lower() == SENDER_EMAIL.lower():
                print(f"\n  ⚠️ Skipping self-email: {email_addr}")
                continue

            if email_addr.lower() == client_email.lower():
                print(f"\n  ⚠️ Skipping client email as recruiter: {email_addr}")
                continue

            subject = generate_subject(lead, candidate)
            body_text = generate_email_body(lead, candidate)
            body_html = generate_email_html_body(lead, candidate)

            print(f"\n  [{sent_count + 1}] {'Drafting' if dry_run else 'Sending'} to: {email_addr}")
            print(f"      Score: {score_lead(lead)}")
            print(f"      Recruiter: {recruiter_name}")
            print(f"      Role: {job_role}")
            print(f"      Resume Category: {role_category}")
            print(f"      Subject: {subject}")

            try:
                result = send_or_draft_safe(
                    service=gmail_service,
                    to=email_addr,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                    attachment_path=attach_path,
                    dry_run=dry_run,
                    cc=client_email,
                )
            except Exception as e:
                result = {"status": "failed", "message_id": "", "error": str(e)}

            status = result.get("status", "failed")
            message_id = result.get("message_id", "")

            log_sent_email(
                recipient_email=email_addr,
                recruiter_name=recruiter_name,
                job_role=job_role,
                subject=subject,
                status=status,
                message_id=message_id,
            )

            if status in ("sent", "drafted"):
                print(f"      ✅ {status.upper()} — ID: {message_id}")
                sent_count += 1
            else:
                print(f"      ❌ FAILED — {result.get('error', 'Unknown error')}")
                failed_count += 1

            if sent_count < max_emails:
                time.sleep(EMAIL_SEND_DELAY + random.uniform(1, 4))

    print("\n" + "=" * 60)
    print("  EMAIL SUMMARY")
    print("=" * 60)
    print(f"  ✅ Successfully {'drafted' if dry_run else 'sent'}: {sent_count}")
    print(f"  ❌ Failed: {failed_count}")
    print("  📄 Sent log: outputs/sent_log.csv")
    print("  📁 Custom resumes: outputs/resumes/")
    print("=" * 60)


def main():
    print_banner()
    args = parse_arguments()

    dry_run = DRY_RUN and not args.send
    keywords = args.keywords or DEFAULT_SEARCH_KEYWORDS
    fallback_resume_path = Path(args.resume) if args.resume else DEFAULT_RESUME_PATH

    print(f"  Mode: {'DRY-RUN' if dry_run else 'LIVE SEND'}")
    print(f"  Fallback Resume: {fallback_resume_path}")
    print(f"  Max emails: {args.max_emails}")
    print(f"  Min lead score: {args.min_score}")

    if not args.skip_scrape:
        step_scrape(keywords)
    else:
        print("\n⏭️ Skipping LinkedIn scrape. Using existing leads.csv.")
        if not LEADS_CSV.exists():
            print("\n❌ Error: leads.csv not found! Run without --skip-scrape first.")
            sys.exit(1)

    unsent_leads = step_preview_and_confirm(args.min_score)

    if unsent_leads is None:
        print("\n👋 Exiting. No emails to process.")
        return

    step_send_emails(unsent_leads, dry_run, fallback_resume_path, args.max_emails)

    print("\n🎉 Automation complete!\n")


if __name__ == "__main__":
    main()