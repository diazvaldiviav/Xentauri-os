"""
Google Docs Module - Google Docs API Integration.

Sprint 3.9: Google Docs Intelligence

This module provides:
- GoogleDocsClient: API client for fetching documents
- GoogleDoc: Pydantic model for document data
- DocContent: Simplified content for AI processing

Usage:
======
    from app.environments.google.docs import GoogleDocsClient, GoogleDoc, DocContent
    
    client = GoogleDocsClient(access_token="ya29.xxx")
    
    # Get full document
    doc = await client.get_document("1abc123...")
    
    # Get text content for AI
    content = await client.get_content_text("1abc123...")
    if content.is_complex():
        # Route to Claude
        ...
"""

from app.environments.google.docs.client import GoogleDocsClient
from app.environments.google.docs.schemas import GoogleDoc, DocContent, DocMetadata

__all__ = [
    "GoogleDocsClient",
    "GoogleDoc",
    "DocContent",
    "DocMetadata",
]
