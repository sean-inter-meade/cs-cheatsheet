from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AuthorType(str, Enum):
    USER = "user"
    LEAD = "lead"
    ADMIN = "admin"
    FIN = "fin"
    BOT = "bot"
    OTHER = "other"


class ConversationMessage(BaseModel):
    id: str
    author_type: AuthorType
    body_text: str       # HTML-stripped plain text
    body_html: str = ""  # Raw HTML (preserved for image extraction)
    created_at: datetime
    conversation_id: str
    author_name: str = ""  # Admin/Fin name for attribution in problem analysis
