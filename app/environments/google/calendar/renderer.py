"""
Calendar HTML Renderer - Generate display-ready HTML for Raspberry Pi.

This module converts Google Calendar events into clean, readable HTML
optimized for display on screens running Chromium in kiosk mode.

Design Goals:
=============
1. Clean, readable typography
2. High contrast for TV/monitor display
3. No JavaScript dependencies (pure HTML/CSS)
4. Responsive layout for different screen sizes
5. Dark mode friendly
6. Auto-refresh via meta tag (optional)

Customization:
==============
The renderer uses a template-based approach, making it easy to:
- Change colors and themes
- Adjust font sizes for different displays
- Add branding or custom headers
- Modify event layout

Usage:
======
    from app.environments.google.calendar import CalendarRenderer
    
    renderer = CalendarRenderer()
    html = renderer.render_events(events, title="Today's Schedule")
    
    # Or render with user info
    html = renderer.render_events(
        events,
        title="John's Calendar",
        user_name="John Doe",
        show_date=True,
    )
"""

from datetime import datetime, timezone
from typing import List, Optional
import html as html_escape

from app.environments.google.calendar.schemas import CalendarEvent


class CalendarRenderer:
    """
    Renders calendar events as HTML for display.
    
    Creates a clean, TV-optimized HTML page from calendar events.
    Designed for Chromium kiosk mode on Raspberry Pi.
    
    Attributes:
        theme: Color theme ("dark" or "light")
        font_size: Base font size in pixels
        refresh_interval: Auto-refresh interval in seconds (0 = disabled)
    """
    
    def __init__(
        self,
        theme: str = "dark",
        font_size: int = 24,
        refresh_interval: int = 300,  # 5 minutes default
    ):
        """
        Initialize the renderer.
        
        Args:
            theme: "dark" or "light" color scheme
            font_size: Base font size in pixels (scales other elements)
            refresh_interval: Seconds between auto-refresh (0 to disable)
        """
        self.theme = theme
        self.font_size = font_size
        self.refresh_interval = refresh_interval
    
    def _get_css(self) -> str:
        """Generate CSS styles based on theme and settings."""
        
        # Theme colors
        if self.theme == "dark":
            bg_color = "#1a1a2e"
            text_color = "#eaeaea"
            accent_color = "#4a90d9"
            card_bg = "#16213e"
            muted_color = "#8a8a9a"
            border_color = "#2a2a4e"
            time_bg = "#0f3460"
        else:
            bg_color = "#f5f5f5"
            text_color = "#1a1a1a"
            accent_color = "#1976d2"
            card_bg = "#ffffff"
            muted_color = "#666666"
            border_color = "#e0e0e0"
            time_bg = "#e3f2fd"
        
        return f"""
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 
                         Oxygen, Ubuntu, Cantarell, sans-serif;
            font-size: {self.font_size}px;
            line-height: 1.5;
            background-color: {bg_color};
            color: {text_color};
            padding: 2rem;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid {border_color};
        }}
        
        h1 {{
            font-size: 2.5rem;
            font-weight: 600;
            color: {accent_color};
        }}
        
        .date-display {{
            font-size: 1.2rem;
            color: {muted_color};
        }}
        
        .events-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .event-card {{
            display: flex;
            background: {card_bg};
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }}
        
        .event-time {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 1rem 1.5rem;
            background: {time_bg};
            min-width: 120px;
            text-align: center;
        }}
        
        .event-time .time {{
            font-size: 1.3rem;
            font-weight: 600;
            color: {accent_color};
        }}
        
        .event-time .duration {{
            font-size: 0.8rem;
            color: {muted_color};
            margin-top: 0.25rem;
        }}
        
        .event-details {{
            flex: 1;
            padding: 1rem 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        
        .event-title {{
            font-size: 1.3rem;
            font-weight: 500;
            color: {text_color};
            margin-bottom: 0.25rem;
        }}
        
        .event-location {{
            font-size: 0.9rem;
            color: {muted_color};
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .event-location::before {{
            content: "📍";
        }}
        
        .all-day-badge {{
            display: inline-block;
            padding: 0.2rem 0.6rem;
            background: {accent_color};
            color: white;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        
        .search-context {{
            background: {time_bg};
            padding: 0.75rem 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            font-size: 0.95rem;
            color: {muted_color};
        }}
        
        .search-context strong {{
            color: {accent_color};
        }}
        
        .no-events {{
            text-align: center;
            padding: 4rem 2rem;
            color: {muted_color};
        }}
        
        .no-events h2 {{
            font-size: 1.5rem;
            margin-bottom: 1rem;
        }}
        
        .no-events p {{
            font-size: 1rem;
        }}
        
        footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid {border_color};
            text-align: center;
            color: {muted_color};
            font-size: 0.8rem;
        }}
        
        /* Animations for loading */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .event-card {{
            animation: fadeIn 0.3s ease-out forwards;
        }}
        
        .event-card:nth-child(1) {{ animation-delay: 0.1s; }}
        .event-card:nth-child(2) {{ animation-delay: 0.15s; }}
        .event-card:nth-child(3) {{ animation-delay: 0.2s; }}
        .event-card:nth-child(4) {{ animation-delay: 0.25s; }}
        .event-card:nth-child(5) {{ animation-delay: 0.3s; }}
        """
    
    def _format_time(self, event: CalendarEvent) -> str:
        """Format event time for display."""
        if event.is_all_day():
            return '<span class="all-day-badge">All Day</span>'
        
        if event.start and event.start.date_time:
            time_str = event.start.date_time.strftime("%I:%M %p").lstrip("0")
            return f'<span class="time">{time_str}</span>'
        
        return '<span class="time">--:--</span>'
    
    def _format_duration(self, event: CalendarEvent) -> str:
        """Calculate and format event duration."""
        if event.is_all_day():
            return ""
        
        if event.start and event.end and event.start.date_time and event.end.date_time:
            duration = event.end.date_time - event.start.date_time
            minutes = int(duration.total_seconds() / 60)
            
            if minutes < 60:
                return f"{minutes} min"
            
            hours = minutes // 60
            remaining_mins = minutes % 60
            
            if remaining_mins == 0:
                return f"{hours} hr"
            return f"{hours}h {remaining_mins}m"
        
        return ""
    
    def _render_event(self, event: CalendarEvent) -> str:
        """Render a single event as HTML."""
        title = html_escape.escape(event.get_display_title())
        time_html = self._format_time(event)
        duration = self._format_duration(event)
        location = html_escape.escape(event.location) if event.location else None
        
        duration_html = f'<span class="duration">{duration}</span>' if duration else ""
        location_html = f'<div class="event-location">{location}</div>' if location else ""
        
        return f"""
        <div class="event-card">
            <div class="event-time">
                {time_html}
                {duration_html}
            </div>
            <div class="event-details">
                <div class="event-title">{title}</div>
                {location_html}
            </div>
        </div>
        """
    
    def render_events(
        self,
        events: List[CalendarEvent],
        title: str = "Calendar",
        user_name: Optional[str] = None,
        show_date: bool = True,
        show_footer: bool = True,
        display_date: Optional[datetime] = None,
        search_term: Optional[str] = None,
    ) -> str:
        """
        Render a list of events as a complete HTML page.
        
        Args:
            events: List of CalendarEvent objects to render
            title: Page title (header text)
            user_name: Optional user name to display
            show_date: Show current date in header
            show_footer: Show footer with last updated time
            display_date: Optional specific date to show in header (defaults to today)
            search_term: Optional search term for context display (Sprint 3.7)
        
        Returns:
            Complete HTML page as a string
        """
        # Build meta tags
        meta_refresh = ""
        if self.refresh_interval > 0:
            meta_refresh = f'<meta http-equiv="refresh" content="{self.refresh_interval}">'
        
        # Build header
        display_title = title
        if user_name:
            display_title = f"{user_name}'s {title}"
        
        date_display = ""
        if show_date:
            # Use provided display_date or fall back to today
            date_to_show = display_date if display_date else datetime.now()
            date_str = date_to_show.strftime("%A, %B %d, %Y")
            date_display = f'<div class="date-display">{date_str}</div>'
        
        # Sprint 3.7: Build search context header
        search_context = ""
        if search_term:
            safe_search = html_escape.escape(search_term)
            search_context = f'<div class="search-context">Showing events matching: <strong>"{safe_search}"</strong></div>'
        
        # Build events list
        if events:
            events_html = "\n".join(self._render_event(event) for event in events)
            events_section = f'<div class="events-list">{events_html}</div>'
        else:
            # Sprint 3.7: Show search-aware no results message
            if search_term:
                safe_search = html_escape.escape(search_term)
                events_section = f"""
            <div class="no-events">
                <h2>No Events Found</h2>
                <p>No events matching "{safe_search}" were found.</p>
            </div>
            """
            else:
                events_section = """
            <div class="no-events">
                <h2>No Upcoming Events</h2>
                <p>Your calendar is clear! Enjoy your free time.</p>
            </div>
            """
        
        # Build footer
        footer_html = ""
        if show_footer:
            now = datetime.now()
            updated_str = now.strftime("%I:%M %p").lstrip("0")
            footer_html = f"""
            <footer>
                Last updated: {updated_str} • Powered by Jarvis
            </footer>
            """
        
        # Assemble complete page
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {meta_refresh}
    <title>{html_escape.escape(display_title)}</title>
    <style>
    {self._get_css()}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{html_escape.escape(display_title)}</h1>
            {date_display}
        </header>
        
        {search_context}
        
        {events_section}
        
        {footer_html}
    </div>
</body>
</html>
"""
    
    def render_error(
        self,
        error_message: str,
        title: str = "Calendar Error",
    ) -> str:
        """
        Render an error page.
        
        Used when calendar data cannot be fetched (e.g., token expired).
        
        Args:
            error_message: Error description to display
            title: Page title
        
        Returns:
            Complete HTML error page as a string
        """
        safe_message = html_escape.escape(error_message)
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>{html_escape.escape(title)}</title>
    <style>
    {self._get_css()}
    .error-container {{
        text-align: center;
        padding: 4rem 2rem;
    }}
    .error-icon {{
        font-size: 4rem;
        margin-bottom: 1rem;
    }}
    .error-message {{
        color: #ef5350;
        font-size: 1.2rem;
        margin-bottom: 1rem;
    }}
    .error-hint {{
        color: #8a8a9a;
        font-size: 0.9rem;
    }}
    </style>
</head>
<body>
    <div class="container">
        <div class="error-container">
            <div class="error-icon">⚠️</div>
            <h1>{html_escape.escape(title)}</h1>
            <p class="error-message">{safe_message}</p>
            <p class="error-hint">This page will automatically retry in 60 seconds.</p>
        </div>
    </div>
</body>
</html>
"""
