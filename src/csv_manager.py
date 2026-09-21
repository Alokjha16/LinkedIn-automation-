
"""
csv_manager.py - CSV Data Management Module
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd

from config import LEADS_CSV, SENT_LOG_CSV

logger = logging.getLogger(__name__)

LEADS_COLUMNS = [
    "recruiter_name",
    "emails",
    "profile_link",
    "post_url",
    "post_time",
    "post_type",
    "job_role",
    "location",
    "full_post_text",
    "post_snippet",
    "scraped_at",
]

SENT_LOG_COLUMNS = [
    "recipient_email",
    "recruiter_name",
    "job_role",
    "subject",
    "status",
    "message_id",
    "sent_at",
]


def save_leads(leads: List[Dict], filepath: Optional[Path] = None) -> Path:
    filepath = filepath or LEADS_CSV

    filepath.parent.mkdir(parents=True, exist_ok=True)

    new_df = pd.DataFrame(leads)

    for col in LEADS_COLUMNS:
        if col not in new_df.columns:
            new_df[col] = ""

    new_df = new_df[LEADS_COLUMNS]

    if filepath.exists():
        existing_df = pd.read_csv(filepath)

        for col in LEADS_COLUMNS:
            if col not in existing_df.columns:
                existing_df[col] = ""

        existing_df = existing_df[LEADS_COLUMNS]
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined_df = new_df

    before_count = len(combined_df)
    combined_df = combined_df.drop_duplicates(subset=["emails"], keep="last")
    after_count = len(combined_df)

    duplicates_removed = before_count - after_count

    if duplicates_removed > 0:
        logger.info(f"Removed {duplicates_removed} duplicate email(s).")
        print(f"   🔄 Removed {duplicates_removed} duplicate email(s).")

    combined_df.to_csv(filepath, index=False, encoding="utf-8-sig")

    logger.info(f"Leads saved to {filepath} ({len(combined_df)} total records).")
    print(f"   💾 Leads saved to {filepath} ({len(combined_df)} records)")

    return filepath


def load_leads(filepath: Optional[Path] = None) -> pd.DataFrame:
    filepath = filepath or LEADS_CSV

    if not filepath.exists():
        logger.warning(f"Leads file not found: {filepath}")
        return pd.DataFrame(columns=LEADS_COLUMNS)

    df = pd.read_csv(filepath)

    for col in LEADS_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[LEADS_COLUMNS]

    logger.info(f"Loaded {len(df)} leads from {filepath}.")
    return df


def get_unsent_leads(filepath: Optional[Path] = None) -> pd.DataFrame:
    """
    Return leads that still contain at least one email that has not been
    successfully sent.

    Important:
    - status='sent' blocks an email
    - status='drafted' does NOT block live sending
    - status='failed' does NOT block retrying
    """

    leads_df = load_leads(filepath)

    if leads_df.empty:
        return leads_df

    successfully_sent_emails = set()

    if SENT_LOG_CSV.exists():
        try:
            sent_df = pd.read_csv(SENT_LOG_CSV)

            if (
                "recipient_email" in sent_df.columns
                and "status" in sent_df.columns
            ):
                successful_rows = sent_df[
                    sent_df["status"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .isin({"sent", "delivered"})
                ]

                successfully_sent_emails = set(
                    successful_rows["recipient_email"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .str.lower()
                )

            elif "recipient_email" in sent_df.columns:
                logger.warning(
                    "sent_log.csv has no status column. "
                    "Ignoring old log entries to avoid blocking valid leads."
                )

        except Exception as e:
            logger.warning(f"Could not read sent log safely: {e}")

    def has_unsent_email(email_str):
        if pd.isna(email_str):
            return False

        emails = [
            email.strip().lower()
            for email in str(email_str).replace(";", ",").split(",")
            if email.strip()
        ]

        return any(
            email not in successfully_sent_emails
            for email in emails
        )

    unsent_df = leads_df[
        leads_df["emails"].apply(has_unsent_email)
    ].copy()

    logger.info(
        f"Found {len(unsent_df)} unsent leads out of "
        f"{len(leads_df)} total. Successfully sent addresses: "
        f"{len(successfully_sent_emails)}"
    )

    return unsent_df


def log_sent_email(
    recipient_email: str,
    recruiter_name: str,
    job_role: str,
    subject: str,
    status: str,
    message_id: str = "",
) -> None:
    SENT_LOG_CSV.parent.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "recipient_email": recipient_email,
        "recruiter_name": recruiter_name,
        "job_role": job_role,
        "subject": subject,
        "status": status,
        "message_id": message_id,
        "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    new_row = pd.DataFrame([log_entry], columns=SENT_LOG_COLUMNS)

    if SENT_LOG_CSV.exists():
        existing_df = pd.read_csv(SENT_LOG_CSV)

        for col in SENT_LOG_COLUMNS:
            if col not in existing_df.columns:
                existing_df[col] = ""

        existing_df = existing_df[SENT_LOG_COLUMNS]
        combined_df = pd.concat([existing_df, new_row], ignore_index=True)
    else:
        combined_df = new_row

    combined_df.to_csv(SENT_LOG_CSV, index=False, encoding="utf-8-sig")
    logger.info(f"Logged email to {recipient_email} (status: {status}).")


def preview_leads(df: pd.DataFrame) -> None:
    if df.empty:
        print("\n📭 No leads to display.")
        return

    print("\n" + "=" * 70)
    print(f"  📋 LEADS PREVIEW ({len(df)} records)")
    print("=" * 70)

    for idx, row in df.iterrows():
        full_text = str(row.get("full_post_text", ""))

        print(f"\n  #{idx + 1}")
        print(f"  Recruiter : {row.get('recruiter_name', 'N/A')}")
        print(f"  Email(s)  : {row.get('emails', 'N/A')}")
        print(f"  Job Role  : {row.get('job_role', 'N/A')}")
        print(f"  Location  : {row.get('location', 'N/A')}")
        print(f"  Post Type : {row.get('post_type', 'N/A')}")
        print(f"  Post Time : {row.get('post_time', 'N/A')}")
        print(f"  JD Chars  : {len(full_text)}")

        snippet = str(row.get("post_snippet", ""))[:120]
        print(f"  Snippet   : {snippet}...")
        print("  " + "-" * 60)

    print()
