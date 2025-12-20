"""
Google Docs Schemas - Data structures for Google Docs operations.

These Pydantic models represent Google Docs API responses
in a clean, typed format for use throughout the application.

Sprint 3.9: Google Docs Intelligence

Reference: https://developers.google.com/docs/api/reference/rest
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DocMetadata(BaseModel):
    """
    Metadata about a Google Doc.
    
    Contains document ID, title, and revision info.
    """
    document_id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    revision_id: Optional[str] = Field(None, alias="revisionId", description="Document revision ID")
    
    class Config:
        populate_by_name = True


class TextRun(BaseModel):
    """
    A contiguous run of text with consistent formatting.
    
    Part of the document content structure.
    """
    content: str = Field("", description="The text content")
    
    class Config:
        populate_by_name = True


class ParagraphElement(BaseModel):
    """
    An element in a paragraph (typically a text run).
    """
    text_run: Optional[TextRun] = Field(None, alias="textRun")
    start_index: Optional[int] = Field(None, alias="startIndex")
    end_index: Optional[int] = Field(None, alias="endIndex")
    
    class Config:
        populate_by_name = True
    
    def get_text(self) -> str:
        """Extract text content from this element."""
        if self.text_run:
            return self.text_run.content
        return ""


class Paragraph(BaseModel):
    """
    A paragraph in the document body.
    """
    elements: List[ParagraphElement] = Field(default_factory=list)
    
    class Config:
        populate_by_name = True
    
    def get_text(self) -> str:
        """Extract all text from this paragraph."""
        return "".join(elem.get_text() for elem in self.elements)


class StructuralElement(BaseModel):
    """
    A structural element in the document body (paragraph, table, etc.).
    """
    paragraph: Optional[Paragraph] = None
    start_index: Optional[int] = Field(None, alias="startIndex")
    end_index: Optional[int] = Field(None, alias="endIndex")
    
    class Config:
        populate_by_name = True
    
    def get_text(self) -> str:
        """Extract text from this structural element."""
        if self.paragraph:
            return self.paragraph.get_text()
        return ""


class DocumentBody(BaseModel):
    """
    The body content of a Google Doc.
    """
    content: List[StructuralElement] = Field(default_factory=list)
    
    class Config:
        populate_by_name = True
    
    def get_full_text(self) -> str:
        """Extract all text content from the document body."""
        return "".join(elem.get_text() for elem in self.content)


class DocContent(BaseModel):
    """
    Content extracted from a Google Doc.
    
    This is a simplified representation for AI processing.
    Contains the plain text and structural information.
    """
    text: str = Field("", description="Plain text content of the document")
    title: str = Field("", description="Document title")
    word_count: int = Field(0, description="Approximate word count")
    char_count: int = Field(0, description="Character count")
    has_images: bool = Field(False, description="Whether document contains images")
    has_tables: bool = Field(False, description="Whether document contains tables")
    has_links: bool = Field(False, description="Whether document contains hyperlinks")
    header_count: int = Field(0, description="Number of headers/sections")
    
    def is_complex(self) -> bool:
        """
        Determine if this document is complex.
        
        Complex documents (>5000 chars OR >10 headers) should be
        routed to Claude for deeper analysis.
        """
        return self.char_count > 5000 or self.header_count > 10
    
    def get_preview(self, max_chars: int = 500) -> str:
        """Get a preview of the document content."""
        if len(self.text) <= max_chars:
            return self.text
        return self.text[:max_chars] + "..."


class GoogleDoc(BaseModel):
    """
    A Google Doc document.
    
    Contains the full document structure from the Docs API.
    
    Reference: https://developers.google.com/docs/api/reference/rest/v1/documents
    """
    document_id: str = Field(..., alias="documentId", description="Unique document identifier")
    title: str = Field(..., description="Document title")
    body: Optional[DocumentBody] = Field(None, description="Document body content")
    revision_id: Optional[str] = Field(None, alias="revisionId")
    
    class Config:
        populate_by_name = True
    
    def get_display_title(self) -> str:
        """Get a display-friendly title (with fallback)."""
        return self.title or "(Untitled Document)"
    
    def get_plain_text(self) -> str:
        """Extract all plain text from the document."""
        if self.body:
            return self.body.get_full_text()
        return ""
    
    def to_doc_content(self) -> DocContent:
        """
        Convert to DocContent for AI processing.
        
        Extracts text and computes metadata for routing decisions.
        """
        text = self.get_plain_text()
        
        # Simple header detection (lines starting with uppercase or ending with :)
        lines = text.split('\n')
        header_count = sum(1 for line in lines if line.strip() and (
            line.strip().isupper() or 
            line.strip().endswith(':') or
            len(line.strip()) < 50 and line.strip() == line.strip().title()
        ))
        
        return DocContent(
            text=text,
            title=self.title,
            word_count=len(text.split()) if text else 0,
            char_count=len(text),
            has_images=False,  # Would need to check inline objects
            has_tables=False,  # Would need to check structural elements
            has_links=False,   # Would need to check text runs for links
            header_count=header_count,
        )


class GoogleDocsResponse(BaseModel):
    """
    Response wrapper for Docs API responses.
    
    Used for paginated list operations (if implemented).
    """
    documents: List[GoogleDoc] = Field(default_factory=list)
    next_page_token: Optional[str] = Field(None, alias="nextPageToken")
    
    class Config:
        populate_by_name = True
