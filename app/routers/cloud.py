"""
Cloud Router - Endpoints for cloud-rendered content for Raspberry Pi.

This router provides endpoints that return rendered HTML content
designed to be displayed on Raspberry Pi screens via WebSocket commands.

The flow is:
1. Raspberry Pi receives "SHOW_CONTENT" command via WebSocket
2. Pi's Chromium browser navigates to the content URL
3. Backend fetches data (e.g., calendar events) and renders HTML
4. Pi displays the rendered page

Endpoints:
==========
- GET /cloud/calendar → Rendered HTML calendar for authenticated user
- GET /cloud/calendar/{user_id} → Calendar for specific user (internal use)

Security:
=========
Calendar endpoints require authentication via:
1. JWT token (Authorization header) - for direct API access
2. Signed content token (query param) - for Pi display/iframe

The content is rendered server-side, so the Pi just displays static HTML.
This is intentional - Pi devices have limited resources and we want
reliable, fast rendering.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.oauth_credential import OAuthCredential
from app.environments.google import GoogleAuthClient, GoogleCalendarClient
from app.environments.google.calendar import CalendarRenderer
from app.environments.base import TokenExpiredError, APIError
from app.services.content_token import content_token_service


logger = logging.getLogger("jarvis.routers.cloud")


# ---------------------------------------------------------------------------
# ROUTER SETUP
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/cloud", tags=["cloud"])


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------


async def _get_valid_google_token(
    user_id: UUID,
    db: Session,
) -> Optional[str]:
    """
    Get a valid Google access token for a user, refreshing if needed.
    
    Args:
        user_id: The user's ID
        db: Database session
    
    Returns:
        Valid access token, or None if not available
    """
    # Get stored credentials
    cred = db.query(OAuthCredential).filter(
        OAuthCredential.user_id == user_id,
        OAuthCredential.provider == "google",
    ).first()
    
    if not cred:
        return None
    
    # Check if token needs refresh
    if cred.is_expired():
        if not cred.refresh_token:
            logger.warning(f"Token expired and no refresh token for user {user_id}")
            return None
        
        # Refresh the token
        try:
            auth_client = GoogleAuthClient()
            new_tokens = await auth_client.refresh_access_token(cred.refresh_token)
            
            # Update stored credentials
            cred.access_token = new_tokens.access_token
            cred.expires_at = new_tokens.expires_at
            if new_tokens.refresh_token:
                cred.refresh_token = new_tokens.refresh_token
            
            db.commit()
            
            logger.info(f"Refreshed Google token for user {user_id}")
            return cred.access_token
            
        except TokenExpiredError as e:
            logger.error(f"Failed to refresh token for user {user_id}: {e}")
            return None
    
    return cred.access_token


# ---------------------------------------------------------------------------
# CALENDAR ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/calendar", response_class=HTMLResponse)
async def get_calendar_html(
    request: Request,
    db: Session = Depends(get_db),
    theme: str = Query("dark", description="Color theme: dark or light"),
    max_events: int = Query(10, description="Maximum events to show", ge=1, le=50),
    view: str = Query("upcoming", description="View type: upcoming, today, week, date"),
    date: Optional[str] = Query(None, description="Specific date (YYYY-MM-DD) for date view"),
    search: Optional[str] = Query(None, description="Search term to filter events by title/description"),
    token: Optional[str] = Query(None, description="Content access token for iframe display"),
):
    """
    Get rendered HTML calendar for the current user.
    
    Returns a complete HTML page with the user's Google Calendar events,
    optimized for display on Raspberry Pi screens.
    
    Sprint 3.6: Added date parameter for showing calendar on specific dates.
    Sprint 3.7: Added search parameter for filtering events by title/description.
    
    Authentication:
        - JWT token in Authorization header (for API calls)
        - OR content token in query param (for iframe/simulator)
    
    Args:
        request: FastAPI request
        db: Database session
        theme: "dark" or "light" color scheme
        max_events: Maximum number of events to display
        view: "upcoming", "today", "week", or "date"
        search: Optional search term to filter events
        date: Specific date in YYYY-MM-DD format (required if view="date")
        token: Optional content access token
    
    Returns:
        HTMLResponse with rendered calendar
    
    Usage:
        1. Via API: GET /cloud/calendar with Authorization header
        2. Via iframe: GET /cloud/calendar?token=<signed_token>
        3. Specific date: GET /cloud/calendar?date=2025-12-06&token=<token>
        4. Search: GET /cloud/calendar?search=birthday&token=<token>
        5. Date + Search: GET /cloud/calendar?date=2025-12-15&search=meeting&token=<token>
    """
    renderer = CalendarRenderer(theme=theme)
    user_id = None
    
    # Try to get user from content token first (for iframe)
    if token:
        user_id = content_token_service.validate(token)
        if not user_id:
            html = renderer.render_error(
                error_message="Invalid or expired content token. Please refresh the page.",
                title="Access Denied",
            )
            return HTMLResponse(content=html, status_code=403)
    else:
        # Try to get user from JWT header
        try:
            from app.core.security import decode_access_token
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                jwt_token = auth_header.split(" ")[1]
                payload = decode_access_token(jwt_token)
                if payload and "sub" in payload:
                    user_id = UUID(payload["sub"])
        except Exception:
            pass
    
    if not user_id:
        html = renderer.render_error(
            error_message="Authentication required. Please log in.",
            title="Not Authenticated",
        )
        return HTMLResponse(content=html, status_code=403)
    
    # Get valid access token for this user
    access_token = await _get_valid_google_token(user_id, db)
    
    if not access_token:
        # No Google account connected or token invalid
        html = renderer.render_error(
            error_message="Google Calendar not connected. Please connect your Google account.",
            title="Calendar Unavailable",
        )
        return HTMLResponse(content=html, status_code=200)
    
    # Get user for display name
    user = db.query(User).filter(User.id == user_id).first()
    display_name = user.display_name if user else "User"
    
    # Fetch calendar events
    try:
        calendar_client = GoogleCalendarClient(access_token=access_token)
        
        # ---------------------------------------------------------------------------
        # SPRINT 3.9: Smart Semantic Search with LLM Matching
        # ---------------------------------------------------------------------------
        # Instead of passing search term to Google API (literal matching),
        # we fetch all events and use LLM for semantic matching.
        # This handles typos, translations, and synonyms.
        if search:
            from app.services.calendar_search_service import calendar_search_service
            
            search_term = search.strip()
            
            # If date is also provided, scope the search to that date
            if date:
                from datetime import datetime
                
                date_obj = None
                parsed_date = None
                
                # Try YYYY-MM-DD format first
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    parsed_date = date
                except ValueError:
                    pass
                
                # Try natural language formats
                if not date_obj:
                    date_lower = date.lower().strip()
                    natural_formats = [
                        "%B %d", "%B %d, %Y", "%b %d", "%b %d, %Y",
                        "%m/%d/%Y", "%m/%d", "%d %B", "%d %B %Y",
                    ]
                    for fmt in natural_formats:
                        try:
                            date_obj = datetime.strptime(date_lower, fmt.lower())
                            if "%Y" not in fmt:
                                date_obj = date_obj.replace(year=datetime.now().year)
                            parsed_date = date_obj.strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            continue
                
                if not date_obj:
                    html = renderer.render_error(
                        error_message=f"Could not parse date '{date}'. Use YYYY-MM-DD format.",
                        title="Invalid Date",
                    )
                    return HTMLResponse(content=html, status_code=400)
                
                # Smart search within the specific date
                search_result = await calendar_search_service.smart_search_with_date(
                    user_query=search_term,
                    user_id=user_id,
                    db=db,
                    date=parsed_date,
                )
            else:
                # Smart search across all future events
                search_result = await calendar_search_service.smart_search(
                    user_query=search_term,
                    user_id=user_id,
                    db=db,
                )
            
            # Handle errors from smart search
            if search_result.error:
                html = renderer.render_error(
                    error_message=search_result.error,
                    title="Search Failed",
                )
                return HTMLResponse(content=html, status_code=200)
            
            events = search_result.events
            
            # Build title with corrected query if different
            if search_result.corrected_query and search_result.corrected_query.lower() != search_term.lower():
                title = f"Events matching '{search_result.corrected_query}' (searched: '{search_term}')"
            else:
                title = f"Events matching '{search_term}'"
            
            # Render with search context
            html = renderer.render_events(
                events=events,
                title=title,
                user_name=display_name,
                show_date=True,
                show_footer=True,
                search_term=search_term,
            )
            
            logger.info(
                f"Smart search for user {user_id}: '{search_term}' -> {len(events)} events",
                extra={
                    "event_count": len(events),
                    "search": search_term,
                    "corrected": search_result.corrected_query,
                    "date": date,
                }
            )
            
            return HTMLResponse(content=html, status_code=200)
        
        # ---------------------------------------------------------------------------
        # SPRINT 3.6: Support date parameter with smart parsing
        # ---------------------------------------------------------------------------
        if date:
            # Specific date requested - try to parse flexibly
            from datetime import datetime
            
            date_obj = None
            parsed_date = None
            
            # Try YYYY-MM-DD format first (preferred)
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                parsed_date = date
            except ValueError:
                pass
            
            # Try natural language formats as fallback
            if not date_obj:
                # Normalize input
                date_lower = date.lower().strip()
                
                # Common natural language formats
                natural_formats = [
                    "%B %d",          # "December 11"
                    "%B %d, %Y",      # "December 11, 2025"
                    "%b %d",          # "Dec 11"
                    "%b %d, %Y",      # "Dec 11, 2025"
                    "%m/%d/%Y",       # "12/11/2025"
                    "%m/%d",          # "12/11"
                    "%d %B",          # "11 December"
                    "%d %B %Y",       # "11 December 2025"
                ]
                
                for fmt in natural_formats:
                    try:
                        date_obj = datetime.strptime(date_lower, fmt.lower())
                        # If year not in format, use current year
                        if "%Y" not in fmt:
                            date_obj = date_obj.replace(year=datetime.now().year)
                        parsed_date = date_obj.strftime("%Y-%m-%d")
                        logger.info(f"Parsed natural date '{date}' as {parsed_date}")
                        break
                    except ValueError:
                        continue
            
            if not date_obj:
                html = renderer.render_error(
                    error_message=f"Could not parse date '{date}'. Use YYYY-MM-DD format (e.g., 2025-12-11).",
                    title="Invalid Date",
                )
                return HTMLResponse(content=html, status_code=400)
            
            # Fetch events for the parsed date
            events = await calendar_client.list_events_for_date(
                date=parsed_date,
                max_results=max_events,
            )
            title = date_obj.strftime("%B %d, %Y")  # e.g., "December 11, 2025"
            
            # Render with the specific date
            html = renderer.render_events(
                events=events,
                title=title,
                user_name=display_name,
                show_date=True,
                show_footer=True,
                display_date=date_obj,
            )
            
            logger.info(
                f"Rendered calendar for user {user_id} for date {parsed_date}",
                extra={"event_count": len(events), "date": parsed_date}
            )
            
            return HTMLResponse(content=html, status_code=200)
        
        # Fetch events based on view type
        elif view == "today":
            events = await calendar_client.list_today_events(max_results=max_events)
            title = "Today's Schedule"
        elif view == "week":
            events = await calendar_client.list_week_events(max_results=max_events)
            title = "This Week"
        else:  # upcoming
            events = await calendar_client.list_upcoming_events(max_results=max_events)
            title = "Upcoming Events"
        
        # Render HTML
        html = renderer.render_events(
            events=events,
            title=title,
            user_name=display_name,
            show_date=True,
            show_footer=True,
        )
        
        logger.info(
            f"Rendered calendar for user {user_id}",
            extra={"event_count": len(events), "view": view, "date": date}
        )
        
        return HTMLResponse(content=html, status_code=200)
        
    except APIError as e:
        logger.error(f"Calendar API error for user {user_id}: {e}")
        html = renderer.render_error(
            error_message=f"Failed to fetch calendar: {str(e)}",
            title="Calendar Error",
        )
        return HTMLResponse(content=html, status_code=200)
    
    except Exception as e:
        logger.exception(f"Unexpected error rendering calendar for user {user_id}")
        html = renderer.render_error(
            error_message="An unexpected error occurred. Please try again.",
            title="Calendar Error",
        )
        return HTMLResponse(content=html, status_code=200)


@router.get("/calendar/preview", response_class=HTMLResponse)
async def get_calendar_preview(
    theme: str = Query("dark", description="Color theme: dark or light"),
):
    """
    Get a preview/demo calendar page without authentication.
    
    Useful for testing the calendar display without Google integration.
    Shows sample events.
    
    Args:
        theme: "dark" or "light" color scheme
    
    Returns:
        HTMLResponse with sample calendar
    """
    from datetime import datetime, timedelta, timezone
    from app.environments.google.calendar.schemas import CalendarEvent, EventTime
    
    # Create sample events
    now = datetime.now(timezone.utc)
    
    sample_events = [
        CalendarEvent(
            id="1",
            summary="Team Standup",
            location="Zoom",
            start=EventTime(dateTime=now.replace(hour=9, minute=0)),
            end=EventTime(dateTime=now.replace(hour=9, minute=30)),
            status="confirmed",
        ),
        CalendarEvent(
            id="2",
            summary="Product Review Meeting",
            location="Conference Room A",
            start=EventTime(dateTime=now.replace(hour=10, minute=0)),
            end=EventTime(dateTime=now.replace(hour=11, minute=0)),
            status="confirmed",
        ),
        CalendarEvent(
            id="3",
            summary="Lunch with Marketing Team",
            location="Cafeteria",
            start=EventTime(dateTime=now.replace(hour=12, minute=30)),
            end=EventTime(dateTime=now.replace(hour=13, minute=30)),
            status="confirmed",
        ),
        CalendarEvent(
            id="4",
            summary="Sprint Planning",
            start=EventTime(dateTime=now.replace(hour=14, minute=0)),
            end=EventTime(dateTime=now.replace(hour=15, minute=30)),
            status="confirmed",
        ),
        CalendarEvent(
            id="5",
            summary="Company All-Hands",
            location="Main Auditorium",
            start=EventTime(date=(now + timedelta(days=1)).strftime("%Y-%m-%d")),
            end=EventTime(date=(now + timedelta(days=1)).strftime("%Y-%m-%d")),
            status="confirmed",
        ),
    ]
    
    renderer = CalendarRenderer(theme=theme, refresh_interval=0)
    html = renderer.render_events(
        events=sample_events,
        title="Preview Calendar",
        user_name="Demo User",
        show_date=True,
        show_footer=True,
    )
    
    return HTMLResponse(content=html, status_code=200)


@router.get("/calendar/status")
async def get_calendar_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check calendar integration status.
    
    Returns information about the user's Google Calendar connection
    and whether calendar display is available.
    
    Args:
        current_user: Authenticated user
        db: Database session
    
    Returns:
        Status information including connection state and event count
    """
    # Check for Google credentials
    cred = db.query(OAuthCredential).filter(
        OAuthCredential.user_id == current_user.id,
        OAuthCredential.provider == "google",
    ).first()
    
    if not cred:
        return {
            "connected": False,
            "status": "not_connected",
            "message": "Google Calendar not connected",
            "calendar_url": None,
        }
    
    # Check if token is valid
    access_token = await _get_valid_google_token(current_user.id, db)
    
    if not access_token:
        return {
            "connected": True,
            "status": "token_expired",
            "message": "Google token expired. Please reconnect.",
            "calendar_url": None,
        }
    
    # Try to fetch calendar info
    try:
        calendar_client = GoogleCalendarClient(access_token=access_token)
        calendars = await calendar_client.list_calendars(max_results=5)
        events = await calendar_client.list_upcoming_events(max_results=5)
        
        return {
            "connected": True,
            "status": "active",
            "message": "Calendar is ready",
            "calendar_count": len(calendars),
            "upcoming_event_count": len(events),
            "calendar_url": "/cloud/calendar",
        }
        
    except APIError as e:
        return {
            "connected": True,
            "status": "error",
            "message": f"Calendar API error: {str(e)}",
            "calendar_url": None,
        }
