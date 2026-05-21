from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from backend.models.cheatsheet import CheatsheetData, Problem, UserInfo
from backend.services.cache import CheatsheetCache
from backend.services.image_extractor import ImageExtractor
from backend.services.intercom_api import IntercomApiService
from backend.services.link_extractor import LinkExtractor
from backend.services.problem_analyzer import ProblemAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter()

_cache = CheatsheetCache()
_api = IntercomApiService()
_analyzer = ProblemAnalyzer()
_img_extractor = ImageExtractor()
_link_extractor = LinkExtractor()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_conversation_id(body: dict[str, Any]) -> str | None:
    conversation = body.get("conversation") or {}
    if isinstance(conversation, dict):
        cid = conversation.get("id") or conversation.get("conversation_id")
        if cid:
            return str(cid)

    context = body.get("context") or {}
    if isinstance(context, dict):
        cid = context.get("conversation_id") or (context.get("conversation") or {}).get("id")
        if cid:
            return str(cid)

    cid = body.get("conversation_id")
    if cid:
        return str(cid)

    logger.warning("No conversation_id found. Payload keys: %s", list(body.keys()))
    return None


def _extract_workspace_id(body: dict[str, Any]) -> str | None:
    for loc in [body, body.get("context") or {}, body.get("conversation") or {}]:
        for key in ("workspace_id", "app_id"):
            val = loc.get(key)
            if val:
                return str(val)
    return None


def _compute_tenure(created_at: datetime | None) -> str:
    if created_at is None:
        return "—"
    now = datetime.now(tz=timezone.utc)
    dt = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    delta_days = max(0, (now - dt).days)
    years = delta_days // 365
    months = (delta_days % 365) // 30
    if years > 0 and months > 0:
        return f"{years}y {months}m"
    if years > 0:
        return f"{years} year{'s' if years != 1 else ''}"
    if months > 0:
        return f"{months} month{'s' if months != 1 else ''}"
    return f"{delta_days} day{'s' if delta_days != 1 else ''}"


def _bool_icon(val: bool | None) -> str:
    if val is True:
        return "✅"
    if val is False:
        return "❌"
    return "—"


# ─── Canvas section renderers ─────────────────────────────────────────────────

def _section_user_info(user: UserInfo) -> list[dict]:
    tenure = _compute_tenure(user.company_created_at)
    return [
        {"type": "text", "text": "*CS Cheatsheet*"},
        {"type": "divider"},
        {"type": "text", "text": f"*{user.name}*"},
        {"type": "text", "text": f"Segment: {user.segment or '—'}   ·   Region: {user.region or '—'}"},
        {"type": "text", "text": f"Settings access: {_bool_icon(user.settings_access)}   ·   Impersonation: {_bool_icon(user.has_impersonation)}"},
        {"type": "text", "text": f"With Intercom: {tenure}"},
        {"type": "divider"},
    ]


def _section_problem_full(problem: Problem, workspace_id: str, number: int, total: int) -> list[dict]:
    """Full problem detail as a flat list of components."""
    components: list[dict] = []

    if total > 1:
        components.append({"type": "text", "text": f"*Problem {number} of {total}*"})
    components.append({"type": "divider"})
    components.append({"type": "text", "text": problem.description})

    if problem.tried:
        components.append({"type": "spacer", "size": "xs"})
        components.append({"type": "text", "text": "*What was tried:*"})
        for step in problem.tried:
            components.append({"type": "text", "text": f"• *{step.attributed_to}:* {step.description}"})

    if problem.next_steps:
        components.append({"type": "spacer", "size": "xs"})
        components.append({"type": "text", "text": "*Possible next steps:*"})
        for step in problem.next_steps:
            components.append({"type": "text", "text": f"• {step}"})

    components.append({"type": "spacer", "size": "xs"})
    ws_url = f"https://intercomrades.intercom.com/admin/apps/{workspace_id}"
    components.append({"type": "text", "text": f"*Workspace:* [{workspace_id}]({ws_url})"})

    if problem.related_links:
        components.append({"type": "divider"})
        components.append({"type": "text", "text": "*Related links:*"})
        components.append({"type": "spacer", "size": "xs"})
        for link in problem.related_links:
            components.append({"type": "text", "text": f"{link.icon} [{link.display_id}]({link.url})"})

    if problem.images:
        components.append({"type": "divider"})
        components.append({"type": "text", "text": "*Images:*"})
        components.append({"type": "spacer", "size": "xs"})
        for img in problem.images:
            components.append({
                "type": "text",
                "text": f"[{img.description}]({img.message_url}) | {img.drplr_url}",
            })

    return components


# ─── Canvas builders ──────────────────────────────────────────────────────────

def _build_main_canvas(data: CheatsheetData) -> dict[str, Any]:
    components: list[dict] = []

    # Section 1: User info
    components.extend(_section_user_info(data.user))

    # Section 2: Problems
    n = len(data.problems)
    if n == 0:
        components.append({"type": "text", "text": "*Problem Summary*"})
        components.append({"type": "divider"})
        components.append({"type": "text", "text": "No problems detected in this conversation."})
        components.append({"type": "divider"})

    elif n == 1:
        components.append({"type": "text", "text": "*Problem Summary*"})
        components.extend(_section_problem_full(data.problems[0], data.user.workspace_id, 1, 1))
        components.append({"type": "divider"})

    else:
        components.append({"type": "text", "text": f"*Problem Summaries ({n})*"})
        components.append({"type": "divider"})
        for i, problem in enumerate(data.problems):
            components.append({"type": "text", "text": f"*{i + 1}.* {problem.summary}"})
            components.append({"type": "spacer", "size": "xs"})
            components.append({
                "type": "button",
                "label": "More info",
                "style": "secondary",
                "id": f"problem_detail:{i}",
                "action": {"type": "submit"},
            })
            components.append({"type": "spacer", "size": "xs"})
        components.append({"type": "divider"})

    # Section 3: Open Tickets
    if data.open_tickets:
        components.append({"type": "text", "text": f"*Open Tickets ({len(data.open_tickets)})*"})
        components.append({"type": "spacer", "size": "xs"})
        for ticket in data.open_tickets:
            components.append({"type": "text", "text": f"• [{ticket.topic}]({ticket.url})"})
    else:
        components.append({"type": "text", "text": "*Open Tickets (0)*"})
        components.append({"type": "spacer", "size": "xs"})
        components.append({"type": "text", "text": "No other open tickets."})

    components.append({"type": "spacer", "size": "m"})
    components.append({
        "type": "button",
        "label": "Refresh",
        "style": "secondary",
        "id": "refresh",
        "action": {"type": "submit"},
    })

    return {"canvas": {"content": {"components": components}, "stored_data": {"current_view": "main"}}}


def _build_problem_detail_canvas(data: CheatsheetData, problem_index: int) -> dict[str, Any]:
    problem = data.problems[problem_index]
    total = len(data.problems)

    components: list[dict] = []
    components.extend(_section_problem_full(problem, data.user.workspace_id, problem_index + 1, total))
    components.append({"type": "spacer", "size": "m"})
    components.append({
        "type": "button",
        "label": "← Back",
        "style": "secondary",
        "id": "back_to_main",
        "action": {"type": "submit"},
    })

    return {
        "canvas": {
            "content": {"components": components},
            "stored_data": {
                "current_view": "problem_detail",
                "problem_index": problem_index,
            },
        }
    }


def _error_canvas(message: str) -> dict[str, Any]:
    return {"canvas": {"content": {"components": [{"type": "text", "text": message}]}}}


# ─── Data pipeline ────────────────────────────────────────────────────────────

def _build_cheatsheet_data(conversation_id: str, workspace_id: str | None) -> CheatsheetData:
    # Fetch conversation to get contacts and resolve workspace_id
    conv_data = _api.get_conversation(conversation_id)
    workspace_id = (
        workspace_id
        or conv_data.get("workspace_id")
        or conv_data.get("app_id")
        or "unknown"
    )

    contacts = (conv_data.get("contacts") or {}).get("contacts") or []
    contact_id = contacts[0].get("id") if contacts else None

    if contact_id:
        user_info = _api.get_contact(contact_id, workspace_id)
        company = _api.get_contact_company(contact_id)
        if company:
            user_info.company_created_at = _api.extract_company_created_at(company)
        open_tickets = _api.get_open_tickets(contact_id, conversation_id, workspace_id)
    else:
        logger.warning("No contact found in conversation %s", conversation_id)
        user_info = UserInfo(name="Unknown", workspace_id=workspace_id)
        open_tickets = []

    messages = _api.get_messages(conversation_id)

    problems = _analyzer.analyze(messages)

    all_images = _img_extractor.extract(messages, workspace_id, conversation_id)
    all_links = _link_extractor.extract(messages)

    # Attach all conversation images and links to every problem so they appear in each detail view
    for problem in problems:
        problem.images = all_images
        problem.related_links = all_links

    return CheatsheetData(user=user_info, problems=problems, open_tickets=open_tickets)


def _get_data(conversation_id: str, workspace_id: str | None) -> CheatsheetData:
    cached = _cache.get(conversation_id)
    if cached is not None:
        logger.info("Cache hit for conversation %s", conversation_id)
        return cached

    data = _build_cheatsheet_data(conversation_id, workspace_id)
    _cache.put(conversation_id, data)
    return data


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/canvas/initialize")
async def canvas_initialize(body: dict[str, Any]) -> dict[str, Any]:
    try:
        conversation_id = _extract_conversation_id(body)
        if not conversation_id:
            return _error_canvas("Error: No conversation_id in payload.")

        workspace_id = _extract_workspace_id(body)
        data = _get_data(conversation_id, workspace_id)
        return _build_main_canvas(data)

    except Exception as exc:
        logger.exception("canvas_initialize failed")
        return _error_canvas(f"Error: {type(exc).__name__}: {exc}")


@router.post("/canvas/submit")
async def canvas_submit(body: dict[str, Any]) -> dict[str, Any]:
    try:
        logger.info("Canvas submit payload keys: %s", list(body.keys()))

        conversation_id = _extract_conversation_id(body)
        if not conversation_id:
            return _error_canvas("Error: No conversation_id in payload.")

        workspace_id = _extract_workspace_id(body)

        clicked = (
            body.get("component_id")
            or body.get("id")
            or (body.get("input_values") or {}).get("component_id")
            or ""
        )
        logger.info("Submit: clicked=%s conversation=%s", clicked, conversation_id)

        if clicked == "refresh":
            _cache.invalidate(conversation_id)

        if clicked.startswith("problem_detail:"):
            try:
                index = int(clicked.split(":")[1])
            except (IndexError, ValueError):
                index = 0
            data = _get_data(conversation_id, workspace_id)
            if 0 <= index < len(data.problems):
                return _build_problem_detail_canvas(data, index)
            return _build_main_canvas(data)

        # "back_to_main", "refresh", or any unknown action → show main
        data = _get_data(conversation_id, workspace_id)
        return _build_main_canvas(data)

    except Exception as exc:
        logger.exception("canvas_submit failed")
        return _error_canvas(f"Error: {type(exc).__name__}: {exc}")
