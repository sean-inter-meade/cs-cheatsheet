from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from backend.models.cheatsheet import ImageRef
from backend.models.conversation import ConversationMessage

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\b\w+\b")


def _short_description(text: str, max_words: int = 5) -> str:
    words = _WORD_RE.findall(text.strip())
    if not words:
        return "attached image"
    return " ".join(words[:max_words])


class ImageExtractor:
    def extract(
        self,
        messages: list[ConversationMessage],
        workspace_id: str,
        conversation_id: str,
    ) -> list[ImageRef]:
        results: list[ImageRef] = []
        conv_url = f"https://app.intercom.com/a/apps/{workspace_id}/conversations/{conversation_id}"

        for msg in messages:
            if not msg.body_html:
                continue
            try:
                soup = BeautifulSoup(msg.body_html, "html.parser")
                for img in soup.find_all("img"):
                    alt = img.get("alt", "").strip()
                    if alt:
                        desc = _short_description(alt)
                    else:
                        # Use text adjacent to the img tag
                        parent_text = img.parent.get_text(separator=" ") if img.parent else ""
                        desc = _short_description(parent_text) if parent_text.strip() else "attached image"

                    results.append(ImageRef(
                        description=desc,
                        message_url=conv_url,
                    ))
            except Exception:
                logger.exception("Failed to extract images from message %s", msg.id)

        return results
