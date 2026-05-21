from __future__ import annotations

from datetime import datetime, timezone

from backend.models.conversation import AuthorType, ConversationMessage
from backend.services.link_extractor import LinkExtractor


def _msg(body_text: str = "", body_html: str = "") -> ConversationMessage:
    return ConversationMessage(
        id="1",
        author_type=AuthorType.ADMIN,
        body_text=body_text,
        body_html=body_html,
        created_at=datetime.now(tz=timezone.utc),
        conversation_id="conv_1",
    )


class TestLinkExtractor:
    def test_extracts_workflow_link(self):
        extractor = LinkExtractor()
        url = "https://app.intercom.com/a/apps/abc/workflows/12345"
        msgs = [_msg(body_html=f'<p>Check <a href="{url}">this workflow</a></p>')]
        links = extractor.extract(msgs)
        assert any(l.url_type == "workflow" and l.display_id == "12345" for l in links)

    def test_extracts_conversation_link(self):
        extractor = LinkExtractor()
        url = "https://app.intercom.com/a/apps/abc/conversations/99999"
        msgs = [_msg(body_text=url)]
        links = extractor.extract(msgs)
        assert any(l.url_type == "conversation" and l.display_id == "99999" for l in links)

    def test_deduplicates_same_url(self):
        extractor = LinkExtractor()
        url = "https://app.intercom.com/a/apps/abc/workflows/1"
        msgs = [_msg(body_text=f"{url} {url}")]
        links = extractor.extract(msgs)
        assert len([l for l in links if l.url == url]) == 1

    def test_skips_non_intercom_urls(self):
        extractor = LinkExtractor()
        msgs = [_msg(body_text="https://github.com/intercom/intercom/issues/123")]
        links = extractor.extract(msgs)
        assert links == []

    def test_workflow_icon(self):
        extractor = LinkExtractor()
        url = "https://app.intercom.com/a/apps/xyz/workflows/555"
        msgs = [_msg(body_text=url)]
        links = extractor.extract(msgs)
        assert links[0].icon == "⚙️"
