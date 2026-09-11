from pathlib import Path

from src.gmail_service import authenticate_gmail, send_or_draft

service = authenticate_gmail()

result = send_or_draft(
    service=service,
    to="rahuljha1229@gmail.com",
    subject="CC Test - Quinn Tracking",
    body_text="Testing CC functionality.",
    attachment_path=None,
    dry_run=True
)

print(result)