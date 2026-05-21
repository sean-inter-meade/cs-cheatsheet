from __future__ import annotations

from datetime import datetime, timezone

from backend.models.conversation import AuthorType, ConversationMessage
from backend.services.image_extractor import ImageExtractor


def _msg_with_html(html: str) -> ConversationMessage:
    return ConversationMessage(
        id="1",
        author_type=AuthorType.USER,
        body_text="",
        body_html=html,
        created_at=datetime.now(tz=timezone.utc),
        conversation_id="conv_1",
    )


class TestImageExtractor:
    def test_extracts_image_with_alt_text(self):
        extractor = ImageExtractor()
        msg = _msg_with_html('<p>See this <img src="https://example.com/a.png" alt="error screenshot showing 500"></p>')
        images = extractor.extract([msg], "app_xyz", "conv_1")
        assert len(images) == 1
        assert "error" in images[0].description.lower()

    def test_extracts_image_without_alt_falls_back_to_parent_text(self):
        extractor = ImageExtractor()
        msg = _msg_with_html('<p>Screenshot of the broken dashboard<img src="https://example.com/b.png"></p>')
        images = extractor.extract([msg], "app_xyz", "conv_1")
        assert len(images) == 1
        assert images[0].description != ""

    def test_no_images_returns_empty(self):
        extractor = ImageExtractor()
        msg = _msg_with_html("<p>No images here, just text.</p>")
        images = extractor.extract([msg], "app_xyz", "conv_1")
        assert images == []

    def test_multiple_images_in_one_message(self):
        extractor = ImageExtractor()
        msg = _msg_with_html(
            '<img src="a.png" alt="first screenshot">'
            '<img src="b.png" alt="second screenshot">'
        )
        images = extractor.extract([msg], "app_xyz", "conv_1")
        assert len(images) == 2

    def test_image_url_links_to_conversation(self):
        extractor = ImageExtractor()
        msg = _msg_with_html('<img src="x.png" alt="test">')
        images = extractor.extract([msg], "app_xyz", "conv_123")
        assert "conv_123" in images[0].message_url
        assert "app_xyz" in images[0].message_url

    def test_drplr_placeholder_set(self):
        extractor = ImageExtractor()
        msg = _msg_with_html('<img src="x.png" alt="test">')
        images = extractor.extract([msg], "app_xyz", "conv_1")
        assert "drplr" in images[0].drplr_url.lower()
