"""Resume storage: DB/[email].pdf inside the server's resume directory."""
import io
import logging
import re
from pathlib import Path

from django.conf import settings
from pypdf import PdfReader

logger = logging.getLogger(__name__)
# Stricter than RFC 5322: the address becomes a file name, so it must not contain path characters.
SAFE_EMAIL = re.compile(r"^[A-Za-z0-9._+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


class ResumeError(ValueError):
    pass


def is_safe_email(email: str) -> bool:
    return bool(SAFE_EMAIL.fullmatch(email or ""))


def resume_path(email: str, directory: Path | None = None) -> Path:
    if not is_safe_email(email):
        raise ResumeError("Email cannot be used as a file name.")
    return Path(directory or settings.RESUME_DIR) / f"{email}.pdf"


def validate_pdf(data: bytes) -> None:
    if len(data) > settings.MAX_RESUME_BYTES:
        raise ResumeError("Resume is larger than the 5 MB limit.")
    if not data.startswith(b"%PDF-"):
        raise ResumeError("Resume must be a PDF file.")


def store_resume(email: str, data: bytes) -> Path:
    validate_pdf(data)
    path = resume_path(email)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def extract_text(data: bytes) -> str:
    """Best-effort text extraction. A scanned or damaged PDF yields an empty string."""
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:  # pypdf raises many unrelated types on malformed files
        logger.warning("Could not read resume text: %s", exc)
        return ""
