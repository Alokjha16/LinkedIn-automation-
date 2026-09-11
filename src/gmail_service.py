"""
gmail_service.py - Gmail API Service Module
"""

import base64
import logging
import mimetypes
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import Optional, Dict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import (
    GMAIL_CREDENTIALS_FILE,
    GMAIL_TOKEN_FILE,
    GMAIL_SCOPES,
    SENDER_EMAIL,
    TRACKING_EMAIL,
)

logger = logging.getLogger(__name__)


def authenticate_gmail():
    creds = None

    if GMAIL_TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_FILE), GMAIL_SCOPES)
            logger.info("Loaded existing Gmail token.")
        except Exception as e:
            logger.warning(f"Failed to load token: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Gmail token refreshed.")
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}. Re-authenticating...")
                creds = None

        if not creds:
            if not GMAIL_CREDENTIALS_FILE.exists():
                raise FileNotFoundError(f"Gmail credentials file not found: {GMAIL_CREDENTIALS_FILE}")

            flow = InstalledAppFlow.from_client_secrets_file(
                str(GMAIL_CREDENTIALS_FILE), GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
            logger.info("New Gmail authentication completed.")

        with open(GMAIL_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        logger.info(f"Token saved to {GMAIL_TOKEN_FILE}.")

    service = build("gmail", "v1", credentials=creds)
    logger.info("Gmail API service initialized successfully.")
    print("✅ Gmail API authenticated successfully!")
    return service


def compose_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    attachment_path: Optional[Path] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = TRACKING_EMAIL,
) -> Dict:
    message = MIMEMultipart("mixed")
    message["To"] = to
    message["From"] = SENDER_EMAIL
    message["Subject"] = subject

    if cc:
        message["Cc"] = cc

    if bcc:
        message["Bcc"] = bcc

    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body_text, "plain", "utf-8"))

    if body_html:
        body_part.attach(MIMEText(body_html, "html", "utf-8"))

    message.attach(body_part)

    if attachment_path:
        attachment_path = Path(attachment_path)

        if attachment_path.exists():
            content_type, _ = mimetypes.guess_type(str(attachment_path))
            if content_type is None:
                content_type = "application/octet-stream"

            main_type, sub_type = content_type.split("/", 1)

            with open(attachment_path, "rb") as f:
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(f.read())

            encoders.encode_base64(attachment)
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=attachment_path.name,
            )

            message.attach(attachment)
            logger.info(f"Attached file: {attachment_path.name}")
        else:
            logger.warning(f"Attachment file not found: {attachment_path}")

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw_message}


def send_email(service, message: Dict) -> Dict:
    try:
        result = service.users().messages().send(userId="me", body=message).execute()
        logger.info(f"Email sent successfully. Message ID: {result['id']}")
        return {"status": "sent", "message_id": result["id"]}

    except HttpError as e:
        logger.error(f"Gmail API error sending email: {e}")
        return {"status": "failed", "error": str(e), "message_id": ""}

    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        return {"status": "failed", "error": str(e), "message_id": ""}


def create_draft(service, message: Dict) -> Dict:
    try:
        draft = service.users().drafts().create(
            userId="me",
            body={"message": message},
        ).execute()

        logger.info(f"Draft created successfully. Draft ID: {draft['id']}")
        return {"status": "drafted", "message_id": draft["id"]}

    except HttpError as e:
        logger.error(f"Gmail API error creating draft: {e}")
        return {"status": "failed", "error": str(e), "message_id": ""}

    except Exception as e:
        logger.error(f"Unexpected error creating draft: {e}")
        return {"status": "failed", "error": str(e), "message_id": ""}


def send_or_draft(
    service,
    to: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    attachment_path: Optional[Path] = None,
    dry_run: bool = True,
    cc: Optional[str] = None,
    bcc: Optional[str] = TRACKING_EMAIL,
) -> Dict:
    message = compose_email(
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        attachment_path=attachment_path,
        cc=cc,
        bcc=bcc,
    )

    if dry_run:
        logger.info(f"DRY RUN: Creating draft for {to} | BCC: {bcc}")
        return create_draft(service, message)

    logger.info(f"SENDING email to {to} | BCC: {bcc}")
    return send_email(service, message)