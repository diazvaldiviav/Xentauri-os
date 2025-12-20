"""
Document Intelligence Service - AI-powered document analysis.

Sprint 3.9: Google Docs Intelligence

This service provides intelligent document analysis that:
- Summarizes documents for quick understanding
- Extracts key points and action items
- Routes complex documents to appropriate AI models
- Integrates with calendar events for context

Architecture:
=============
1. Receive document content (from GoogleDocsClient)
2. Check complexity to determine AI model
3. Simple docs (< 5000 chars) → Gemini (fast, cheap)
4. Complex docs (> 5000 chars or many headers) → Claude (deep analysis)
5. Return structured analysis

Usage:
======
    from app.services.doc_intelligence_service import doc_intelligence_service
    
    summary = await doc_intelligence_service.summarize_document(
        doc_content=doc.to_doc_content(),
        question="What are the action items?",
    )
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.oauth_credential import OAuthCredential
from app.environments.google.docs import GoogleDocsClient, DocContent
from app.environments.base import APIError
from app.ai.providers import gemini_provider, anthropic_provider
from app.ai.prompts.doc_prompts import (
    build_summary_prompt,
    build_key_points_prompt,
    build_meeting_doc_prompt,
    truncate_content,
)


logger = logging.getLogger("jarvis.services.doc_intelligence")


# ---------------------------------------------------------------------------
# RESULT DATACLASSES
# ---------------------------------------------------------------------------

@dataclass
class DocumentSummary:
    """Result of document summarization."""
    summary: str
    title: str
    word_count: int
    is_complex: bool
    model_used: str  # "gemini" or "claude"
    error: Optional[str] = None


@dataclass
class DocumentKeyPoints:
    """Result of key point extraction."""
    key_points: List[str]
    action_items: List[Dict[str, Any]]
    mentions: List[str]
    document_type: str
    error: Optional[str] = None


@dataclass
class MeetingDocSummary:
    """Result of meeting document analysis."""
    summary: str
    meeting_title: str
    doc_title: str
    key_points: List[str]
    action_items: List[Dict[str, Any]]
    error: Optional[str] = None


@dataclass
class ExtractedMeetingDetails:
    """Meeting details extracted from a document for calendar event creation."""
    event_title: str
    event_date: Optional[str] = None  # YYYY-MM-DD
    event_time: Optional[str] = None  # HH:MM 24-hour
    duration_minutes: int = 60
    location: Optional[str] = None
    attendees: List[str] = None
    description: Optional[str] = None
    error: Optional[str] = None
    needs_clarification: bool = False
    missing_fields: List[str] = None
    
    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []
        if self.missing_fields is None:
            self.missing_fields = []


# ---------------------------------------------------------------------------
# COMPLEXITY THRESHOLDS
# ---------------------------------------------------------------------------

# Documents larger than this go to Claude for deeper analysis
COMPLEXITY_CHAR_THRESHOLD = 5000

# Documents with more headers than this go to Claude
COMPLEXITY_HEADER_THRESHOLD = 10


# ---------------------------------------------------------------------------
# SERVICE CLASS
# ---------------------------------------------------------------------------

class DocIntelligenceService:
    """
    Service for intelligent document analysis using LLMs.
    
    This service orchestrates document analysis by:
    1. Determining document complexity
    2. Routing to appropriate AI model
    3. Parsing and returning structured results
    """
    
    def __init__(self):
        """Initialize the document intelligence service."""
        logger.info("Document intelligence service initialized")
    
    def is_complex_document(self, doc_content: DocContent) -> bool:
        """
        Determine if a document is complex enough to need Claude.
        
        Complex documents:
        - > 5000 characters
        - > 10 headers/sections
        
        Args:
            doc_content: The document content to analyze
        
        Returns:
            True if complex, False if simple
        """
        return (
            doc_content.char_count > COMPLEXITY_CHAR_THRESHOLD or
            doc_content.header_count > COMPLEXITY_HEADER_THRESHOLD
        )
    
    async def summarize_document(
        self,
        doc_content: DocContent,
        question: Optional[str] = None,
    ) -> DocumentSummary:
        """
        Summarize a document using AI.
        
        Routes to Gemini for simple docs, Claude for complex ones.
        
        Args:
            doc_content: The document content to summarize
            question: Optional specific question about the document
        
        Returns:
            DocumentSummary with the AI-generated summary
        """
        is_complex = self.is_complex_document(doc_content)
        
        task = question or "Provide a brief summary of this document."
        
        # Truncate content to fit context limits
        content = truncate_content(doc_content.text)
        
        prompt = build_summary_prompt(
            title=doc_content.title,
            content=content,
            task=task,
        )
        
        try:
            if is_complex:
                # Use Claude for complex documents
                logger.info(f"Using Claude for complex document ({doc_content.char_count} chars)")
                response = await anthropic_provider.generate(
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=1024,
                )
                model_used = "claude"
            else:
                # Use Gemini for simple documents
                logger.info(f"Using Gemini for simple document ({doc_content.char_count} chars)")
                response = await gemini_provider.generate(
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=1024,
                )
                model_used = "gemini"
            
            if not response.success:
                logger.error(f"AI summarization failed: {response.error}")
                return DocumentSummary(
                    summary="",
                    title=doc_content.title,
                    word_count=doc_content.word_count,
                    is_complex=is_complex,
                    model_used=model_used,
                    error=response.error,
                )
            
            return DocumentSummary(
                summary=response.content,
                title=doc_content.title,
                word_count=doc_content.word_count,
                is_complex=is_complex,
                model_used=model_used,
            )
        
        except Exception as e:
            logger.error(f"Document summarization failed: {e}")
            return DocumentSummary(
                summary="",
                title=doc_content.title,
                word_count=doc_content.word_count,
                is_complex=is_complex,
                model_used="none",
                error=str(e),
            )
    
    async def extract_key_points(
        self,
        doc_content: DocContent,
    ) -> DocumentKeyPoints:
        """
        Extract key points from a document.
        
        Always uses Gemini with JSON mode for structured output.
        
        Args:
            doc_content: The document content to analyze
        
        Returns:
            DocumentKeyPoints with extracted information
        """
        content = truncate_content(doc_content.text)
        
        prompt = build_key_points_prompt(
            title=doc_content.title,
            content=content,
        )
        
        try:
            response = await gemini_provider.generate_json(
                prompt=prompt,
                temperature=0.2,
            )
            
            if not response.success:
                logger.error(f"Key points extraction failed: {response.error}")
                return DocumentKeyPoints(
                    key_points=[],
                    action_items=[],
                    mentions=[],
                    document_type="unknown",
                    error=response.error,
                )
            
            # Parse JSON response
            try:
                data = json.loads(response.content)
            except json.JSONDecodeError:
                # Try to extract from text if JSON parsing fails
                data = {
                    "key_points": [response.content],
                    "action_items": [],
                    "mentions": [],
                    "document_type": "general",
                }
            
            return DocumentKeyPoints(
                key_points=data.get("key_points", []),
                action_items=data.get("action_items", []),
                mentions=data.get("mentions", []),
                document_type=data.get("document_type", "general"),
            )
        
        except Exception as e:
            logger.error(f"Key points extraction failed: {e}")
            return DocumentKeyPoints(
                key_points=[],
                action_items=[],
                mentions=[],
                document_type="unknown",
                error=str(e),
            )
    
    async def summarize_meeting_doc(
        self,
        meeting_title: str,
        meeting_time: str,
        doc_content: DocContent,
        user_question: Optional[str] = None,
    ) -> MeetingDocSummary:
        """
        Summarize a document in the context of a meeting.
        
        This provides a more contextual summary, highlighting
        information relevant to the meeting.
        
        Args:
            meeting_title: Title of the calendar event
            meeting_time: When the meeting is scheduled
            doc_content: The linked document content
            user_question: Optional specific question
        
        Returns:
            MeetingDocSummary with contextual analysis
        """
        is_complex = self.is_complex_document(doc_content)
        content = truncate_content(doc_content.text)
        
        question = user_question or "What should I know before this meeting?"
        
        prompt = build_meeting_doc_prompt(
            meeting_title=meeting_title,
            meeting_time=meeting_time,
            doc_title=doc_content.title,
            doc_content=content,
            user_question=question,
        )
        
        try:
            if is_complex:
                logger.info(f"Using Claude for complex meeting doc")
                response = await anthropic_provider.generate(
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=1024,
                )
            else:
                logger.info(f"Using Gemini for simple meeting doc")
                response = await gemini_provider.generate(
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=1024,
                )
            
            if not response.success:
                return MeetingDocSummary(
                    summary="",
                    meeting_title=meeting_title,
                    doc_title=doc_content.title,
                    key_points=[],
                    action_items=[],
                    error=response.error,
                )
            
            # Also extract key points for structured data
            key_points_result = await self.extract_key_points(doc_content)
            
            return MeetingDocSummary(
                summary=response.content,
                meeting_title=meeting_title,
                doc_title=doc_content.title,
                key_points=key_points_result.key_points,
                action_items=key_points_result.action_items,
            )
        
        except Exception as e:
            logger.error(f"Meeting doc summarization failed: {e}")
            return MeetingDocSummary(
                summary="",
                meeting_title=meeting_title,
                doc_title=doc_content.title,
                key_points=[],
                action_items=[],
                error=str(e),
            )
    
    async def get_document_for_user(
        self,
        doc_id: str,
        user_id: UUID,
        db: Session,
    ) -> Optional[DocContent]:
        """
        Fetch a document for a user using their OAuth credentials.
        
        Args:
            doc_id: Google Doc ID
            user_id: User's UUID
            db: Database session
        
        Returns:
            DocContent if successful, None if failed
        
        Raises:
            APIError: With user-friendly error message
        """
        # Get user's Google credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            logger.warning(f"No Google credentials for user {user_id}")
            raise APIError(
                "Please reconnect Google to allow document access.",
                status_code=401,
            )
        
        # Check if user has docs scope
        scopes = credentials.scopes or []
        has_docs_scope = any("documents" in s.lower() for s in scopes)
        
        if not has_docs_scope:
            logger.warning(f"User {user_id} lacks documents scope")
            raise APIError(
                "Please reconnect Google to allow document access.",
                status_code=403,
            )
        
        # Fetch the document
        docs_client = GoogleDocsClient(access_token=credentials.access_token)
        return await docs_client.get_content_text(doc_id)
    
    async def extract_meeting_details(
        self,
        doc_content: DocContent,
    ) -> ExtractedMeetingDetails:
        """
        Extract meeting details from document for calendar event creation.
        
        Uses LLM to parse document and extract:
        - Title, date, time, duration
        - Location and attendees
        - Description/agenda
        
        Args:
            doc_content: Document content to analyze
        
        Returns:
            ExtractedMeetingDetails with parsed information
        """
        from app.ai.prompts.doc_prompts import build_meeting_extraction_prompt, truncate_content
        
        # Truncate content for LLM context
        content = truncate_content(doc_content.text, max_chars=10000)
        prompt = build_meeting_extraction_prompt(doc_content.title, content)
        
        try:
            # Use Gemini for extraction (fast, consistent JSON output)
            response = await gemini_provider.generate(
                prompt=prompt,
                temperature=0.1,  # Low temp for consistent extraction
            )
            
            if not response.success:
                logger.error(f"Meeting extraction failed: {response.error}")
                return ExtractedMeetingDetails(
                    event_title=doc_content.title,
                    error=response.error,
                )
            
            # Parse JSON response
            try:
                # Extract JSON from response (may have markdown code blocks)
                content_text = response.content
                if "```json" in content_text:
                    content_text = content_text.split("```json")[1].split("```")[0]
                elif "```" in content_text:
                    content_text = content_text.split("```")[1].split("```")[0]
                
                data = json.loads(content_text.strip())
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse meeting extraction JSON: {e}")
                return ExtractedMeetingDetails(
                    event_title=doc_content.title,
                    error=f"Could not parse meeting details from document",
                )
            
            # Check for missing required fields
            missing = []
            if not data.get("event_date"):
                missing.append("date")
            if not data.get("event_time"):
                missing.append("time")
            
            return ExtractedMeetingDetails(
                event_title=data.get("event_title") or doc_content.title,
                event_date=data.get("event_date"),
                event_time=data.get("event_time"),
                duration_minutes=data.get("duration_minutes", 60),
                location=data.get("location"),
                attendees=data.get("attendees", []),
                description=data.get("description"),
                needs_clarification=len(missing) > 0,
                missing_fields=missing,
            )
            
        except Exception as e:
            logger.error(f"Meeting extraction failed: {e}")
            return ExtractedMeetingDetails(
                event_title=doc_content.title,
                error=str(e),
            )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

doc_intelligence_service = DocIntelligenceService()
