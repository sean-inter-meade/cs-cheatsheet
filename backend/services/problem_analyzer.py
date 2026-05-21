from __future__ import annotations

import json
import logging

from backend.config.settings import OPENAI_API_KEY
from backend.models.cheatsheet import Problem, TriedStep
from backend.models.conversation import AuthorType, ConversationMessage

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a support engineer assistant at Intercom. Analyze the following customer support conversation and identify the distinct problems the customer is experiencing.

For each problem:
1. Write a 1-2 sentence summary (used in a list view)
2. Write a detailed description paragraph (used in a drilldown view)
3. List what has been tried — note who tried it: "Fin" for the Fin AI bot, the teammate's actual name for support agents, or "Customer" for the user
4. Suggest 2-4 possible next steps a support engineer could take

Return ONLY a JSON object with this exact structure (no markdown, no extra text):
{
  "problems": [
    {
      "summary": "1-2 sentence description of the problem",
      "description": "Detailed paragraph explaining the full scope of the problem",
      "tried": [
        {"description": "What was attempted", "attributed_to": "Fin|{name}|Customer"}
      ],
      "next_steps": ["Action to take", "Another action"]
    }
  ]
}

If there are no clear problems (e.g. just a greeting), return {"problems": []}."""

_FALLBACK_SUMMARY = "Customer reached out with a support request."


def _build_transcript(messages: list[ConversationMessage]) -> str:
    lines = []
    for msg in messages:
        if not msg.body_text.strip():
            continue
        if msg.author_type in (AuthorType.FIN, AuthorType.BOT):
            label = "Fin"
        elif msg.author_type == AuthorType.ADMIN:
            label = f"Agent ({msg.author_name})" if msg.author_name else "Agent"
        elif msg.author_type in (AuthorType.USER, AuthorType.LEAD):
            label = "Customer"
        else:
            label = "System"
        lines.append(f"[{label}]: {msg.body_text.strip()}")
    return "\n".join(lines)


class ProblemAnalyzer:
    def analyze(self, messages: list[ConversationMessage]) -> list[Problem]:
        if not OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured; using fallback problem extraction")
            return self._fallback(messages)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)

            transcript = _build_transcript(messages)
            if not transcript.strip():
                return []

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Conversation:\n\n{transcript}"},
                ],
                temperature=0.2,
                max_tokens=1500,
            )

            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)
            return self._parse(data)

        except Exception:
            logger.exception("OpenAI problem analysis failed; using fallback")
            return self._fallback(messages)

    def _parse(self, data: dict) -> list[Problem]:
        problems = []
        for item in data.get("problems", []):
            tried = [
                TriedStep(
                    description=t.get("description", ""),
                    attributed_to=t.get("attributed_to", "Unknown"),
                )
                for t in item.get("tried", [])
                if t.get("description")
            ]
            problems.append(Problem(
                summary=item.get("summary", _FALLBACK_SUMMARY),
                description=item.get("description", item.get("summary", _FALLBACK_SUMMARY)),
                tried=tried,
                next_steps=[s for s in item.get("next_steps", []) if s],
            ))
        return problems

    def _fallback(self, messages: list[ConversationMessage]) -> list[Problem]:
        user_messages = [
            m for m in messages
            if m.author_type in (AuthorType.USER, AuthorType.LEAD)
            and m.body_text.strip()
        ]
        if not user_messages:
            return []
        first = user_messages[0].body_text.strip()
        summary = first[:200] + "..." if len(first) > 200 else first
        return [Problem(summary=summary, description=first)]
