from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.models.conversation import AuthorType, ConversationMessage
from backend.services.problem_analyzer import ProblemAnalyzer


def _msg(author_type: AuthorType, body: str, name: str = "") -> ConversationMessage:
    return ConversationMessage(
        id="1",
        author_type=author_type,
        body_text=body,
        created_at=datetime.now(tz=timezone.utc),
        conversation_id="conv_1",
        author_name=name,
    )


class TestProblemAnalyzerFallback:
    """Tests for fallback behavior when OpenAI is unavailable."""

    def test_fallback_extracts_first_user_message(self, monkeypatch):
        monkeypatch.setattr("backend.services.problem_analyzer.OPENAI_API_KEY", "")
        analyzer = ProblemAnalyzer()
        messages = [
            _msg(AuthorType.ADMIN, "Hello, how can I help?", "Sarah"),
            _msg(AuthorType.USER, "My workflow 12345 is broken and never triggers"),
        ]
        problems = analyzer.analyze(messages)
        assert len(problems) == 1
        assert "workflow" in problems[0].summary.lower() or "broken" in problems[0].summary.lower()

    def test_fallback_empty_when_no_user_messages(self, monkeypatch):
        monkeypatch.setattr("backend.services.problem_analyzer.OPENAI_API_KEY", "")
        analyzer = ProblemAnalyzer()
        messages = [_msg(AuthorType.ADMIN, "Just an admin message")]
        problems = analyzer.analyze(messages)
        assert problems == []

    def test_fallback_truncates_long_summary(self, monkeypatch):
        monkeypatch.setattr("backend.services.problem_analyzer.OPENAI_API_KEY", "")
        analyzer = ProblemAnalyzer()
        long_msg = "x" * 500
        messages = [_msg(AuthorType.USER, long_msg)]
        problems = analyzer.analyze(messages)
        assert len(problems[0].summary) <= 203  # 200 + "..."
