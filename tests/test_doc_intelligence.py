"""
Tests for Google Docs Intelligence (Sprint 3.9).

Tests the doc intelligence service, meeting link service,
and doc query intent handlers.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.intent_service import IntentService, IntentResult, IntentResultType
from app.ai.intent.schemas import (
    ActionType,
    IntentType,
    DocQueryIntent,
)


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def intent_service():
    """Create an IntentService instance for testing."""
    return IntentService()


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return uuid4()


@pytest.fixture
def sample_doc_url():
    """Sample Google Docs URL."""
    return "https://docs.google.com/document/d/abc123xyz/edit"


@pytest.fixture
def sample_event_id():
    """Sample calendar event ID."""
    return "event-abc123"


# ---------------------------------------------------------------------------
# GOOGLE DOCS CLIENT TESTS
# ---------------------------------------------------------------------------

class TestGoogleDocsClient:
    """Tests for GoogleDocsClient."""
    
    def test_validate_doc_url_valid(self):
        """Valid Google Docs URL should be validated."""
        from app.environments.google.docs import GoogleDocsClient
        
        valid_urls = [
            "https://docs.google.com/document/d/abc123/edit",
            "https://docs.google.com/document/d/xyz789/view",
            "https://docs.google.com/document/d/1234567890abcdef",
        ]
        
        for url in valid_urls:
            assert GoogleDocsClient.validate_doc_url(url) is True
    
    def test_validate_doc_url_invalid(self):
        """Invalid URLs should not be validated."""
        from app.environments.google.docs import GoogleDocsClient
        
        invalid_urls = [
            "https://google.com/document/d/abc123",
            "https://docs.google.com/spreadsheets/d/abc123",
            "https://example.com/doc",
            "not a url",
            "",
        ]
        
        for url in invalid_urls:
            assert GoogleDocsClient.validate_doc_url(url) is False
    
    def test_extract_doc_id(self):
        """Extract doc ID from URL."""
        from app.environments.google.docs import GoogleDocsClient
        
        url = "https://docs.google.com/document/d/abc123xyz/edit"
        doc_id = GoogleDocsClient.extract_doc_id(url)
        assert doc_id == "abc123xyz"
    
    def test_extract_doc_id_no_suffix(self):
        """Extract doc ID from URL without /edit suffix."""
        from app.environments.google.docs import GoogleDocsClient
        
        url = "https://docs.google.com/document/d/abc123xyz"
        doc_id = GoogleDocsClient.extract_doc_id(url)
        assert doc_id == "abc123xyz"


# ---------------------------------------------------------------------------
# DOC INTELLIGENCE SERVICE TESTS
# ---------------------------------------------------------------------------

class TestDocIntelligenceService:
    """Tests for DocIntelligenceService."""
    
    def test_is_complex_document_by_length(self):
        """Documents over 5000 chars should be complex."""
        from app.services.doc_intelligence_service import DocIntelligenceService
        from app.environments.google.docs import DocContent
        
        service = DocIntelligenceService()
        
        # Short doc - simple
        short_content = DocContent(
            title="Test",
            text="This is a short document.",
            paragraphs=[],
            headers=[],
            char_count=25,
            word_count=5,
        )
        assert service.is_complex_document(short_content) is False
        
        # Long doc - complex
        long_content = DocContent(
            title="Test",
            text="a" * 5001,
            paragraphs=[],
            headers=[],
            char_count=5001,
            word_count=1000,
        )
        assert service.is_complex_document(long_content) is True
    
    def test_is_complex_document_by_headers(self):
        """Documents with 10+ headers should be complex."""
        from app.services.doc_intelligence_service import DocIntelligenceService
        from app.environments.google.docs import DocContent
        
        service = DocIntelligenceService()
        
        # Few headers - simple
        few_headers_content = DocContent(
            title="Test",
            text="Short content",
            header_count=3,
            char_count=100,
            word_count=10,
        )
        assert service.is_complex_document(few_headers_content) is False
        
        # Many headers - complex
        many_headers_content = DocContent(
            title="Test",
            text="Short content",
            header_count=11,
            char_count=100,
            word_count=10,
        )
        assert service.is_complex_document(many_headers_content) is True
    
    def test_is_complex_document_boundary(self):
        """Test boundary conditions."""
        from app.services.doc_intelligence_service import DocIntelligenceService
        from app.environments.google.docs import DocContent
        
        service = DocIntelligenceService()
        
        # Exactly 5000 chars - still simple
        boundary_content = DocContent(
            title="Test",
            text="a" * 5000,
            paragraphs=[],
            headers=[],
            char_count=5000,
            word_count=1000,
        )
        assert service.is_complex_document(boundary_content) is False
        
        # Exactly 10 headers - still simple
        ten_headers_content = DocContent(
            title="Test",
            text="short",
            paragraphs=[],
            headers=[f"Header {i}" for i in range(10)],
            char_count=100,
            word_count=10,
        )
        assert service.is_complex_document(ten_headers_content) is False


# ---------------------------------------------------------------------------
# MEETING LINK SERVICE TESTS
# ---------------------------------------------------------------------------

class TestMeetingLinkService:
    """Tests for MeetingLinkService."""
    
    def test_extract_doc_id_from_url(self, sample_doc_url):
        """Extract doc ID from valid URL."""
        from app.services.meeting_link_service import MeetingLinkService
        
        service = MeetingLinkService()
        doc_id = service.extract_doc_id_from_url(sample_doc_url)
        assert doc_id == "abc123xyz"
    
    def test_extract_doc_id_from_invalid_url(self):
        """Return None for invalid URL."""
        from app.services.meeting_link_service import MeetingLinkService
        
        service = MeetingLinkService()
        doc_id = service.extract_doc_id_from_url("https://example.com/not-a-doc")
        assert doc_id is None


# ---------------------------------------------------------------------------
# DOC QUERY INTENT HANDLER TESTS
# ---------------------------------------------------------------------------

class TestHandleDocQuery:
    """Tests for _handle_doc_query."""
    
    @pytest.mark.asyncio
    async def test_handle_link_doc_no_url(
        self, intent_service, mock_db, sample_user_id
    ):
        """Missing doc URL should return error."""
        intent = DocQueryIntent(
            original_text="link this doc to my meeting",
            confidence=0.95,
            action=ActionType.LINK_DOC,
            doc_url=None,
            meeting_search="meeting",
        )
        
        result = await intent_service._handle_link_doc(
            request_id="req-123",
            intent=intent,
            user_id=sample_user_id,
            start_time=0,
            db=mock_db,
        )
        
        assert result.success is False
        assert "provide a Google Docs URL" in result.message
    
    @pytest.mark.asyncio
    async def test_handle_link_doc_invalid_url(
        self, intent_service, mock_db, sample_user_id
    ):
        """Invalid doc URL should return error."""
        intent = DocQueryIntent(
            original_text="link this doc to my meeting https://example.com/not-a-doc",
            confidence=0.95,
            action=ActionType.LINK_DOC,
            doc_url="https://example.com/not-a-doc",
            meeting_search="meeting",
        )
        
        result = await intent_service._handle_link_doc(
            request_id="req-123",
            intent=intent,
            user_id=sample_user_id,
            start_time=0,
            db=mock_db,
        )
        
        assert result.success is False
        assert "Invalid Google Docs URL" in result.message
    
    @pytest.mark.asyncio
    async def test_handle_open_doc_no_meeting(
        self, intent_service, mock_db, sample_user_id
    ):
        """Missing meeting search should return error."""
        intent = DocQueryIntent(
            original_text="open the meeting doc",
            confidence=0.95,
            action=ActionType.OPEN_DOC,
        )
        
        result = await intent_service._handle_open_doc(
            request_id="req-123",
            intent=intent,
            user_id=sample_user_id,
            start_time=0,
            db=mock_db,
        )
        
        assert result.success is False
        assert "specify which meeting" in result.message
    
    @pytest.mark.asyncio
    async def test_handle_read_doc_no_url(
        self, intent_service, mock_db, sample_user_id
    ):
        """Missing doc URL should return error."""
        intent = DocQueryIntent(
            original_text="read this doc",
            confidence=0.95,
            action=ActionType.READ_DOC,
        )
        
        result = await intent_service._handle_read_doc(
            request_id="req-123",
            intent=intent,
            user_id=sample_user_id,
            start_time=0,
            db=mock_db,
        )
        
        assert result.success is False
        assert "provide a Google Docs URL" in result.message
    
    @pytest.mark.asyncio
    async def test_handle_summarize_meeting_doc_no_url(
        self, intent_service, mock_db, sample_user_id
    ):
        """Missing doc URL should return error."""
        intent = DocQueryIntent(
            original_text="summarize this doc",
            confidence=0.95,
            action=ActionType.SUMMARIZE_MEETING_DOC,
        )
        
        result = await intent_service._handle_summarize_meeting_doc(
            request_id="req-123",
            intent=intent,
            user_id=sample_user_id,
            start_time=0,
            db=mock_db,
        )
        
        assert result.success is False
        assert "provide a Google Docs URL" in result.message


# ---------------------------------------------------------------------------
# DOC QUERY INTENT SCHEMA TESTS
# ---------------------------------------------------------------------------

class TestDocQueryIntentSchema:
    """Tests for DocQueryIntent schema."""
    
    def test_doc_query_intent_creation(self, sample_doc_url):
        """DocQueryIntent should be created with correct fields."""
        intent = DocQueryIntent(
            original_text="summarize this doc",
            confidence=0.95,
            action=ActionType.SUMMARIZE_MEETING_DOC,
            doc_url=sample_doc_url,
            question="What are the key points?",
        )
        
        assert intent.intent_type == IntentType.DOC_QUERY
        assert intent.action == ActionType.SUMMARIZE_MEETING_DOC
        assert intent.doc_url == sample_doc_url
        assert intent.question == "What are the key points?"
    
    def test_doc_query_intent_with_meeting(self, sample_doc_url):
        """DocQueryIntent should support meeting search fields."""
        intent = DocQueryIntent(
            original_text="link doc to meeting",
            confidence=0.95,
            action=ActionType.LINK_DOC,
            doc_url=sample_doc_url,
            meeting_search="standup",
            meeting_time="3pm",
        )
        
        assert intent.meeting_search == "standup"
        assert intent.meeting_time == "3pm"
    
    def test_doc_query_intent_minimal(self):
        """DocQueryIntent should work with minimal fields."""
        intent = DocQueryIntent(
            original_text="open meeting doc",
            confidence=0.90,
            action=ActionType.OPEN_DOC,
        )
        
        assert intent.intent_type == IntentType.DOC_QUERY
        assert intent.action == ActionType.OPEN_DOC
        assert intent.doc_url is None
        assert intent.meeting_search is None


# ---------------------------------------------------------------------------
# PARSER INTEGRATION TESTS
# ---------------------------------------------------------------------------

class TestIntentParserDocQuery:
    """Tests for doc query intent parsing."""
    
    def test_map_action_link_doc(self):
        """link_doc action should map to LINK_DOC."""
        from app.ai.intent.parser import IntentParser
        
        parser = IntentParser()
        action = parser._map_action("link_doc")
        assert action == ActionType.LINK_DOC
    
    def test_map_action_open_doc(self):
        """open_doc action should map to OPEN_DOC."""
        from app.ai.intent.parser import IntentParser
        
        parser = IntentParser()
        action = parser._map_action("open_doc")
        assert action == ActionType.OPEN_DOC
    
    def test_map_action_read_doc(self):
        """read_doc action should map to READ_DOC."""
        from app.ai.intent.parser import IntentParser
        
        parser = IntentParser()
        action = parser._map_action("read_doc")
        assert action == ActionType.READ_DOC
    
    def test_map_action_summarize_meeting_doc(self):
        """summarize_meeting_doc action should map to SUMMARIZE_MEETING_DOC."""
        from app.ai.intent.parser import IntentParser
        
        parser = IntentParser()
        action = parser._map_action("summarize_meeting_doc")
        assert action == ActionType.SUMMARIZE_MEETING_DOC
