"""Shared normalization helpers for pipeline modules."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urldefrag, urlparse

UNKNOWN = "unknown"


LEGAL_SUFFIXES = {
    "brasil",
    "company",
    "inc",
    "ltda",
    "sa",
    "startup",
    "startups",
    "tecnologia",
}
LEGAL_SUFFIX_PHRASES = (
    ("s", "a"),
)


def normalize_text(value: str) -> str:
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    return without_accents.lower().strip()


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_startup_name(name: str) -> str:
    normalized = normalize_text(name)
    normalized = re.sub(r"[^\w\s-]", " ", normalized)
    normalized = normalize_whitespace(normalized)
    tokens = _strip_legal_suffixes(normalized.split())
    return " ".join(tokens) or UNKNOWN


def normalize_url(url: str) -> str:
    if url == UNKNOWN or not url.strip():
        return UNKNOWN

    defragged_url, _fragment = urldefrag(url.strip())
    parsed = urlparse(defragged_url)
    if not parsed.scheme and not parsed.netloc:
        parsed = urlparse(f"https://{defragged_url}")
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path
    if path == "/":
        path = ""
    else:
        path = path.rstrip("/")
    return parsed._replace(scheme=scheme, netloc=netloc, path=path, params="", query="", fragment="").geturl()


def _strip_legal_suffixes(tokens: list[str]) -> list[str]:
    stripped = list(tokens)
    changed = True
    while changed and stripped:
        changed = False
        for suffix_phrase in LEGAL_SUFFIX_PHRASES:
            suffix_length = len(suffix_phrase)
            if tuple(stripped[-suffix_length:]) == suffix_phrase:
                del stripped[-suffix_length:]
                changed = True
                break
        if stripped and stripped[-1] in LEGAL_SUFFIXES:
            stripped.pop()
            changed = True
    return stripped


def normalize_domain(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    host = parsed.netloc.lower().removeprefix("www.")
    if not host:
        return UNKNOWN

    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"com", "net", "org", "gov"} and parts[-1] == "br":
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def origin_url(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    if not parsed.netloc:
        return UNKNOWN
    return f"{parsed.scheme}://{parsed.netloc}"
