"""Validate the page snapshot sent by the extension. It comes from an arbitrary web page."""
import re
from urllib.parse import urlsplit

MAX_TEXT = 20000
MAX_FIELDS = 200
MAX_OPTIONS = 300
MAX_BUTTONS = 50
MAX_STRING = 500
FIELD_TYPES = {"text", "email", "tel", "url", "number", "date", "search", "textarea", "select", "radio", "checkbox",
               "file"}


INSTRUCTION_LIKE = re.compile(
    r"ignore\b.{0,40}\b(instruction|prompt|above|previous|prior)|disregard\b.{0,40}\b(instruction|prompt|above|previous)"
    r"|\b(system|developer) (note|prompt|message)|\bai (assistant|model|agent)s?\b|\blanguage models?\b"
    r"|\bprompt injection\b|\bnew instructions?\b",
    re.IGNORECASE,
)


class DomError(ValueError):
    pass


def untrusted_job_text(text: str) -> str:
    """Prepare page text for a prompt: drop sentences aimed at AI models, and anything like a delimiter.

    This reduces prompt injection but cannot eliminate it, so model output is checked as well.
    """
    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    kept = " ".join(s for s in sentences if not INSTRUCTION_LIKE.search(s))
    return kept.replace("<", " ").replace(">", " ")


def is_http_url(url) -> bool:
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def _string(value, limit: int = MAX_STRING) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _option(raw):
    if not isinstance(raw, dict):
        return None
    option = {"value": _string(raw.get("value")), "label": _string(raw.get("label"))}
    if not option["label"]:
        option["label"] = option["value"]
    if raw.get("selector"):
        option["selector"] = _string(raw["selector"])
    return option if option["label"] else None


def _field(raw):
    if not isinstance(raw, dict) or raw.get("type") not in FIELD_TYPES:
        return None  # password and hidden inputs are never accepted
    selector = _string(raw.get("selector"))
    if not selector:
        return None
    options = raw.get("options") if isinstance(raw.get("options"), list) else []
    return {
        "selector": selector,
        "type": raw["type"],
        "label": _string(raw.get("label")),
        "name": _string(raw.get("name")),
        "placeholder": _string(raw.get("placeholder")),
        "required": raw.get("required") is True,
        "options": [o for o in map(_option, options[:MAX_OPTIONS]) if o],
    }


def _button(raw):
    if not isinstance(raw, dict) or not _string(raw.get("selector")):
        return None
    return {"selector": _string(raw["selector"]), "text": _string(raw.get("text")), "type": _string(raw.get("type"))}


def normalize_dom(raw) -> dict:
    if not isinstance(raw, dict):
        raise DomError("Page data must be an object.")
    fields = raw.get("fields") if isinstance(raw.get("fields"), list) else []
    buttons = raw.get("buttons") if isinstance(raw.get("buttons"), list) else []
    return {
        "title": _string(raw.get("title")),
        "text": _string(raw.get("text"), MAX_TEXT),
        "fields": [f for f in map(_field, fields[:MAX_FIELDS]) if f],
        "buttons": [b for b in map(_button, buttons[:MAX_BUTTONS]) if b],
    }
