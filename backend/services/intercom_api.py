from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.config.settings import (
    CDA_COMPANY_CREATED_AT_KEY,
    CDA_IMPERSONATION_KEY,
    CDA_REGION_KEY,
    CDA_SEGMENT_KEY,
    CDA_SETTINGS_ACCESS_KEY,
    INTERCOM_API_BASE,
    INTERCOM_API_TOKEN,
)
from backend.models.cheatsheet import Ticket, UserInfo
from backend.models.conversation import AuthorType, ConversationMessage

logger = logging.getLogger(__name__)

_AUTHOR_TYPE_MAP: dict[str, AuthorType] = {
    "user": AuthorType.USER,
    "lead": AuthorType.LEAD,
    "admin": AuthorType.ADMIN,
    "bot": AuthorType.BOT,
    "fin": AuthorType.FIN,
}

_HTML_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    text = _HTML_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _map_author_type(raw: str) -> AuthorType:
    return _AUTHOR_TYPE_MAP.get(raw.lower(), AuthorType.OTHER)


def _epoch_to_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


class IntercomApiService:
    def __init__(
        self,
        api_token: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self._token = api_token or INTERCOM_API_TOKEN
        self._base = (api_base or INTERCOM_API_BASE).rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Intercom-Version": "2.11",
            "Accept": "application/json",
        }

    def _get(self, path: str) -> dict:
        if not self._token:
            logger.error("No Intercom API token configured")
            return {}
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{self._base}{path}", headers=self._headers)
            response.raise_for_status()
            return response.json()

    def _post(self, path: str, payload: dict) -> dict:
        if not self._token:
            logger.error("No Intercom API token configured")
            return {}
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self._base}{path}",
                headers={**self._headers, "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def get_conversation(self, conversation_id: str) -> dict:
        try:
            return self._get(f"/conversations/{conversation_id}")
        except Exception:
            logger.exception("Failed to fetch conversation %s", conversation_id)
            return {}

    def get_messages(self, conversation_id: str) -> list[ConversationMessage]:
        try:
            data = self._get(f"/conversations/{conversation_id}")
        except Exception:
            logger.exception("Failed to fetch messages for conversation %s", conversation_id)
            return []

        messages: list[ConversationMessage] = []

        source = data.get("source", {})
        source_body_html = source.get("body", "") or ""
        source_author = source.get("author", {})
        source_id = str(source.get("id", "")) or f"{conversation_id}_source"
        source_created_at = _epoch_to_dt(data.get("created_at")) or datetime.now(tz=timezone.utc)

        messages.append(ConversationMessage(
            id=source_id,
            author_type=_map_author_type(source_author.get("type", "")),
            body_text=_strip_html(source_body_html),
            body_html=source_body_html,
            created_at=source_created_at,
            conversation_id=conversation_id,
            author_name=source_author.get("name", ""),
        ))

        parts = data.get("conversation_parts", {}).get("conversation_parts", [])
        for part in parts:
            body_html = part.get("body", "") or ""
            body_text = _strip_html(body_html)
            if not body_text:
                continue
            author = part.get("author", {})
            created_at = _epoch_to_dt(part.get("created_at")) or datetime.now(tz=timezone.utc)
            messages.append(ConversationMessage(
                id=str(part["id"]),
                author_type=_map_author_type(author.get("type", "")),
                body_text=body_text,
                body_html=body_html,
                created_at=created_at,
                conversation_id=conversation_id,
                author_name=author.get("name", ""),
            ))

        messages.sort(key=lambda m: m.created_at)
        return messages

    def get_contact(self, contact_id: str, workspace_id: str) -> UserInfo:
        try:
            data = self._get(f"/contacts/{contact_id}")
        except Exception:
            logger.exception("Failed to fetch contact %s", contact_id)
            return UserInfo(name="Unknown", workspace_id=workspace_id)

        name = data.get("name") or data.get("email") or "Unknown"
        attrs = data.get("custom_attributes") or {}

        def _bool(val: Any) -> bool | None:
            if val is None:
                return None
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.lower() in ("true", "yes", "1")
            return bool(val)

        return UserInfo(
            name=name,
            workspace_id=workspace_id,
            segment=attrs.get(CDA_SEGMENT_KEY) or None,
            region=attrs.get(CDA_REGION_KEY) or None,
            settings_access=_bool(attrs.get(CDA_SETTINGS_ACCESS_KEY)),
            has_impersonation=_bool(attrs.get(CDA_IMPERSONATION_KEY)),
        )

    def get_contact_company(self, contact_id: str) -> dict | None:
        try:
            data = self._get(f"/contacts/{contact_id}/companies")
            companies = data.get("data") or data.get("companies") or []
            if not companies:
                return None
            company_id = companies[0].get("id")
            if not company_id:
                return companies[0]
            return self._get(f"/companies/{company_id}")
        except Exception:
            logger.exception("Failed to fetch company for contact %s", contact_id)
            return None

    def extract_company_created_at(self, company: dict) -> datetime | None:
        attrs = company.get("custom_attributes") or {}
        cda_val = attrs.get(CDA_COMPANY_CREATED_AT_KEY)
        if cda_val is not None:
            dt = _epoch_to_dt(cda_val)
            if dt:
                return dt
        return _epoch_to_dt(company.get("created_at"))

    def get_open_tickets(
        self, contact_id: str, exclude_conversation_id: str, workspace_id: str
    ) -> list[Ticket]:
        try:
            data = self._post("/conversations/search", {
                "query": {
                    "operator": "AND",
                    "value": [
                        {"field": "state", "operator": "=", "value": "open"},
                        {"field": "contacts.id", "operator": "=", "value": contact_id},
                    ],
                },
                "pagination": {"per_page": 20},
            })
        except Exception:
            logger.exception("Failed to search open tickets for contact %s", contact_id)
            return []

        tickets: list[Ticket] = []
        conversations = data.get("conversations") or data.get("data") or []

        for conv in conversations:
            cid = str(conv.get("id", ""))
            if cid == exclude_conversation_id:
                continue

            # Topic: try conversation topics first, then subject, then message preview
            topic = None
            conv_attrs = conv.get("conversation_attributes") or {}
            topics_list = conv_attrs.get("topics") or []
            if topics_list:
                topic = topics_list[0].get("name")

            if not topic:
                source = conv.get("source") or {}
                topic = source.get("subject") or None

            if not topic:
                source = conv.get("source") or {}
                preview = _strip_html(source.get("body", "") or "")
                topic = (preview[:60] + "...") if len(preview) > 60 else preview or f"Conversation {cid}"

            url = f"https://app.intercom.com/a/apps/{workspace_id}/conversations/{cid}"
            tickets.append(Ticket(conversation_id=cid, topic=topic, url=url))

        return tickets
