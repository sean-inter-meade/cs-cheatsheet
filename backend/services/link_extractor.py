from __future__ import annotations

import re
from urllib.parse import urlparse

from backend.models.cheatsheet import LinkRef
from backend.models.conversation import ConversationMessage

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
_ID_RE = re.compile(r"^[0-9a-f]{16,}$|^\d+$")

_TYPE_PATTERNS: list[tuple[str, str, str]] = [
    # (path_keyword, url_type, icon)
    ("workflows", "workflow", "⚙️"),
    ("custom-actions", "custom_action", "⚡"),
    ("conversations", "conversation", "💬"),
    ("procedures", "procedure", "🧪"),
    ("guidance", "guidance", "🧭"),
    ("outbound", "outbound", "📤"),
    ("knowledge-hub", "knowledge_hub", "📚"),
    ("series", "series", "🔄"),
    ("reports", "report", "📊"),
    ("users", "user", "👤"),
    ("companies", "company", "🏢"),
    ("articles", "article", "📄"),
    ("help-center", "help_center", "📖"),
]

_EXCLUDED_HOSTS = {"github.com", "loom.com"}


def _categorize(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()

    if host in _EXCLUDED_HOSTS:
        return "other", "🔗"

    for keyword, url_type, icon in _TYPE_PATTERNS:
        if keyword in path:
            return url_type, icon

    if "intercom" in host:
        return "intercom", "🔗"

    return "other", "🔗"


def _extract_display_id(path: str) -> str:
    segments = [s for s in path.strip("/").split("/") if s]
    numeric = next((s for s in reversed(segments) if s.isdigit()), None)
    if numeric:
        return numeric
    hex_id = next((s for s in reversed(segments) if _ID_RE.match(s)), None)
    if hex_id:
        return hex_id
    return segments[-1] if segments else "link"


class LinkExtractor:
    def extract(self, messages: list[ConversationMessage]) -> list[LinkRef]:
        seen: set[str] = set()
        results: list[LinkRef] = []

        for msg in messages:
            text = msg.body_text or ""
            html = msg.body_html or ""
            for url in _URL_RE.findall(html or text):
                url = url.rstrip(".,;:!?)")
                if url in seen:
                    continue
                seen.add(url)

                parsed = urlparse(url)
                host = (parsed.hostname or "").lower()
                # Skip non-Intercom URLs for the related links section
                if "intercom" not in host and "intercomrades" not in host:
                    continue

                url_type, icon = _categorize(url)
                display_id = _extract_display_id(parsed.path)
                results.append(LinkRef(
                    url=url,
                    display_id=display_id,
                    icon=icon,
                    url_type=url_type,
                ))

        return results
