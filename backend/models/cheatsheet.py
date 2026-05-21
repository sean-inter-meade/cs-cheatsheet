from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UserInfo:
    name: str
    workspace_id: str
    segment: str | None = None
    region: str | None = None
    settings_access: bool | None = None
    has_impersonation: bool | None = None
    company_created_at: datetime | None = None


@dataclass
class TriedStep:
    description: str
    attributed_to: str  # "Fin", teammate name, or "Customer"


@dataclass
class ImageRef:
    description: str    # 4-5 word description
    message_url: str    # link to conversation containing the image
    drplr_url: str = "[drplr - coming soon]"


@dataclass
class LinkRef:
    url: str
    display_id: str
    icon: str
    url_type: str


@dataclass
class Problem:
    summary: str
    description: str
    tried: list[TriedStep] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    related_links: list[LinkRef] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)


@dataclass
class Ticket:
    conversation_id: str
    topic: str
    url: str


@dataclass
class CheatsheetData:
    user: UserInfo
    problems: list[Problem]
    open_tickets: list[Ticket]
