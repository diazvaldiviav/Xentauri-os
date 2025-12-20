"""
Google Docs API Client - Fetch and read Google Docs content.

This client provides methods to interact with the Google Docs API.
It handles API requests, error handling, and response parsing.

Sprint 3.9: Google Docs Intelligence

Key Features:
=============
1. Fetch document content by ID
2. Extract plain text for AI processing
3. Validate Google Doc URLs
4. Clean error handling with specific messages

API Reference:
==============
- Documents API: https://developers.google.com/docs/api/reference/rest/v1/documents

Usage Example:
==============
    from app.environments.google.docs import GoogleDocsClient
    
    client = GoogleDocsClient(access_token="ya29.xxx")
    
    # Get document content
    doc = await client.get_document("1abc123...")
    print(f"Title: {doc.title}")
    print(f"Content: {doc.get_plain_text()}")
"""

import logging
import re
from typing import Optional

import httpx

from app.environments.base import EnvironmentService, APIError
from app.environments.google.docs.schemas import (
    GoogleDoc,
    DocContent,
)


logger = logging.getLogger("jarvis.environments.google.docs")


# ---------------------------------------------------------------------------
# ERROR MESSAGES (from Error Handling Matrix)
# ---------------------------------------------------------------------------
ERROR_NOT_FOUND = "I couldn't find that document. Please check the URL."
ERROR_NO_PERMISSION = "I can't access that document. Please check sharing permissions."
ERROR_INVALID_URL = "That doesn't look like a valid Google Doc URL."
ERROR_MISSING_SCOPE = "Please reconnect Google to allow document access."


class GoogleDocsClient(EnvironmentService):
    """
    Google Docs API client.
    
    Provides methods to fetch and read Google Doc content.
    Requires a valid access token with documents.readonly scope.
    
    Attributes:
        access_token: Google OAuth access token with docs scope
        
    Example:
        client = GoogleDocsClient(access_token="ya29.xxx")
        doc = await client.get_document("1abc123...")
    """
    
    # Service identification
    service_name = "docs"
    required_scopes = [
        "https://www.googleapis.com/auth/documents.readonly",
    ]
    
    # Google Docs API base URL
    BASE_URL = "https://docs.googleapis.com/v1"
    
    # Regex patterns for extracting document IDs from URLs
    # Matches: https://docs.google.com/document/d/{docId}/edit
    DOC_URL_PATTERN = re.compile(
        r"(?:https?://)?docs\.google\.com/document/d/([a-zA-Z0-9_-]+)"
    )
    
    # Also matches: https://docs.google.com/open?id={docId}
    DOC_OPEN_PATTERN = re.compile(
        r"(?:https?://)?docs\.google\.com/open\?id=([a-zA-Z0-9_-]+)"
    )
    
    def __init__(self, access_token: str):
        """
        Initialize the Docs client.
        
        Args:
            access_token: Valid Google OAuth access token with docs scope
        """
        self.access_token = access_token
        self._http_client: Optional[httpx.AsyncClient] = None
    
    # -------------------------------------------------------------------------
    # HTTP CLIENT MANAGEMENT
    # -------------------------------------------------------------------------
    
    def _get_headers(self) -> dict:
        """Get authorization headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Make an authenticated request to the Docs API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., "/documents/{documentId}")
            params: Query parameters
        
        Returns:
            Parsed JSON response
        
        Raises:
            APIError: If the request fails with user-friendly message
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )
                
                # Handle specific error codes with user-friendly messages
                if response.status_code == 401:
                    logger.error("Docs API: Unauthorized (token may be expired)")
                    raise APIError(
                        ERROR_MISSING_SCOPE,
                        status_code=401,
                        response=response.text,
                    )
                
                if response.status_code == 403:
                    logger.error("Docs API: Forbidden (no permission or scope)")
                    # Check if it's a scope issue or permission issue
                    error_text = response.text.lower()
                    if "scope" in error_text or "insufficient" in error_text:
                        raise APIError(
                            ERROR_MISSING_SCOPE,
                            status_code=403,
                            response=response.text,
                        )
                    raise APIError(
                        ERROR_NO_PERMISSION,
                        status_code=403,
                        response=response.text,
                    )
                
                if response.status_code == 404:
                    logger.error("Docs API: Document not found")
                    raise APIError(
                        ERROR_NOT_FOUND,
                        status_code=404,
                        response=response.text,
                    )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Docs API error: {response.status_code} - {error_detail}")
                    raise APIError(
                        f"API request failed: {error_detail}",
                        status_code=response.status_code,
                        response=error_detail,
                    )
                
                return response.json()
                
            except httpx.RequestError as e:
                logger.error(f"Network error in Docs API: {e}")
                raise APIError(f"Network error: {e}")
    
    # -------------------------------------------------------------------------
    # DOCUMENT OPERATIONS
    # -------------------------------------------------------------------------
    
    async def get_document(self, document_id: str) -> GoogleDoc:
        """
        Fetch a Google Doc by its ID.
        
        Args:
            document_id: The document's unique identifier
        
        Returns:
            GoogleDoc object with full document content
        
        Raises:
            APIError: If document not found or access denied
        
        Example:
            doc = await client.get_document("1abc123...")
            print(doc.title)
            print(doc.get_plain_text())
        """
        logger.info(f"Fetching document: {document_id[:10]}...")
        
        endpoint = f"/documents/{document_id}"
        
        data = await self._make_request("GET", endpoint)
        
        doc = GoogleDoc.model_validate(data)
        logger.info(f"Fetched document: {doc.title}")
        
        return doc
    
    async def get_content_text(self, document_id: str) -> DocContent:
        """
        Fetch document and extract text content for AI processing.
        
        This is a convenience method that fetches the document and
        converts it to a DocContent object ready for LLM analysis.
        
        Args:
            document_id: The document's unique identifier
        
        Returns:
            DocContent with extracted text and metadata
        
        Example:
            content = await client.get_content_text("1abc123...")
            if content.is_complex():
                # Route to Claude for deep analysis
            else:
                # Use Gemini for simple summary
        """
        doc = await self.get_document(document_id)
        return doc.to_doc_content()
    
    # -------------------------------------------------------------------------
    # URL VALIDATION
    # -------------------------------------------------------------------------
    
    @classmethod
    def validate_doc_url(cls, url: str) -> bool:
        """
        Check if a string is a valid Google Doc URL.
        
        Args:
            url: The URL to validate
        
        Returns:
            True if valid Google Doc URL, False otherwise
        
        Example:
            if GoogleDocsClient.validate_doc_url(url):
                doc_id = GoogleDocsClient.extract_doc_id(url)
        """
        if not url:
            return False
        
        return bool(cls.DOC_URL_PATTERN.search(url) or cls.DOC_OPEN_PATTERN.search(url))
    
    @classmethod
    def extract_doc_id(cls, url: str) -> Optional[str]:
        """
        Extract document ID from a Google Doc URL.
        
        Supports multiple URL formats:
        - https://docs.google.com/document/d/{docId}/edit
        - https://docs.google.com/document/d/{docId}/view
        - https://docs.google.com/open?id={docId}
        
        Args:
            url: Google Doc URL
        
        Returns:
            Document ID if found, None otherwise
        
        Raises:
            APIError: If URL is invalid
        
        Example:
            doc_id = GoogleDocsClient.extract_doc_id(
                "https://docs.google.com/document/d/1abc123/edit"
            )
            # Returns: "1abc123"
        """
        if not url:
            raise APIError(ERROR_INVALID_URL, status_code=400)
        
        # Try standard document URL pattern
        match = cls.DOC_URL_PATTERN.search(url)
        if match:
            return match.group(1)
        
        # Try open URL pattern
        match = cls.DOC_OPEN_PATTERN.search(url)
        if match:
            return match.group(1)
        
        # If it looks like a raw ID (alphanumeric with - or _), accept it
        if re.match(r"^[a-zA-Z0-9_-]{20,}$", url.strip()):
            return url.strip()
        
        raise APIError(ERROR_INVALID_URL, status_code=400)

    # -------------------------------------------------------------------------
    # ACCESS VALIDATION
    # -------------------------------------------------------------------------
    
    async def validate_access(self, access_token: str) -> bool:
        """
        Verify the access token is valid for document operations.
        
        Makes a lightweight API call to check if the token works.
        
        Args:
            access_token: OAuth access token to validate
        
        Returns:
            True if token is valid and has documents access
        """
        # Temporarily update token for this check
        original_token = self.access_token
        self.access_token = access_token
        
        try:
            # Try to get a document with an invalid ID
            # 404 means token is valid but doc doesn't exist (expected)
            # 401/403 means token is invalid
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/documents/invalid-doc-id-for-validation",
                    headers=self._get_headers(),
                    timeout=10.0,
                )
                # 404 means token is valid but doc doesn't exist (expected)
                # 401/403 means token is invalid
                return response.status_code in (404, 200)
        except Exception:
            return False
        finally:
            # Restore original token
            self.access_token = original_token
