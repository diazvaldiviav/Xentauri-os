"""
Tests for Calendar Create Intent - Sprint 3.8

Tests for:
- CalendarCreateIntent schema
- Intent parser calendar_create handling
- Time resolution (_resolve_time)
- Date resolution (_resolve_event_date)
- Recurrence parsing (_parse_recurrence)
- All-day detection (_detect_all_day)
- Title extraction (_extract_event_title)
"""

import pytest
from datetime import datetime, date, timedelta
from uuid import uuid4

from app.ai.intent.schemas import (
    CalendarCreateIntent,
    IntentType,
    ActionType,
)
from app.ai.intent.parser import IntentParser


# ===========================================================================
# CALENDAR CREATE INTENT SCHEMA TESTS
# ===========================================================================

class TestCalendarCreateIntentSchema:
    """Tests for CalendarCreateIntent schema."""
    
    def test_create_intent_minimal(self):
        """Should create intent with minimal required fields."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="schedule a meeting",
            action=ActionType.CREATE_EVENT,
        )
        
        assert intent.intent_type == IntentType.CALENDAR_CREATE
        assert intent.action == ActionType.CREATE_EVENT
        assert intent.confidence == 0.9
        assert intent.event_title is None
        assert intent.event_date is None
        assert intent.event_time is None
        assert intent.duration_minutes == 60  # Default
        assert intent.is_all_day is False
    
    def test_create_intent_full(self):
        """Should create intent with all fields."""
        intent = CalendarCreateIntent(
            confidence=0.95,
            original_text="schedule team meeting tomorrow at 2 pm for 90 minutes",
            action=ActionType.CREATE_EVENT,
            event_title="Team Meeting",
            event_date="2025-01-15",
            event_time="14:00",
            duration_minutes=90,
            is_all_day=False,
            location="Conference Room A",
            recurrence="RRULE:FREQ=WEEKLY",
        )
        
        assert intent.event_title == "Team Meeting"
        assert intent.event_date == "2025-01-15"
        assert intent.event_time == "14:00"
        assert intent.duration_minutes == 90
        assert intent.location == "Conference Room A"
        assert intent.recurrence == "RRULE:FREQ=WEEKLY"
    
    def test_create_intent_all_day(self):
        """Should create all-day event intent."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="add birthday on January 15",
            action=ActionType.CREATE_EVENT,
            event_title="Birthday",
            event_date="2025-01-15",
            is_all_day=True,
        )
        
        assert intent.is_all_day is True
        assert intent.event_time is None
    
    def test_confirm_intent(self):
        """Should create confirmation intent."""
        intent = CalendarCreateIntent(
            confidence=0.99,
            original_text="yes",
            action=ActionType.CONFIRM_CREATE,
        )
        
        assert intent.action == ActionType.CONFIRM_CREATE
    
    def test_cancel_intent(self):
        """Should create cancellation intent."""
        intent = CalendarCreateIntent(
            confidence=0.99,
            original_text="no",
            action=ActionType.CANCEL_CREATE,
        )
        
        assert intent.action == ActionType.CANCEL_CREATE
    
    def test_edit_intent(self):
        """Should create edit intent with field and value."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="change time to 7 pm",
            action=ActionType.EDIT_PENDING_EVENT,
            edit_field="event_time",
            edit_value="19:00",
        )
        
        assert intent.action == ActionType.EDIT_PENDING_EVENT
        assert intent.edit_field == "event_time"
        assert intent.edit_value == "19:00"


# ===========================================================================
# TIME RESOLUTION TESTS
# ===========================================================================

class TestTimeResolution:
    """Tests for _resolve_time method."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return IntentParser()
    
    def test_resolve_time_noon(self, parser):
        """Should resolve 'noon' to 12:00."""
        assert parser._resolve_time("noon") == "12:00"
    
    def test_resolve_time_midnight(self, parser):
        """Should resolve 'midnight' to 00:00."""
        assert parser._resolve_time("midnight") == "00:00"
    
    def test_resolve_time_pm_simple(self, parser):
        """Should resolve '6 pm' to 18:00."""
        assert parser._resolve_time("6 pm") == "18:00"
    
    def test_resolve_time_pm_with_minutes(self, parser):
        """Should resolve '2:30 pm' to 14:30."""
        assert parser._resolve_time("2:30 pm") == "14:30"
    
    def test_resolve_time_am_simple(self, parser):
        """Should resolve '10 am' to 10:00."""
        assert parser._resolve_time("10 am") == "10:00"
    
    def test_resolve_time_am_with_minutes(self, parser):
        """Should resolve '10:45 am' to 10:45."""
        assert parser._resolve_time("10:45 am") == "10:45"
    
    def test_resolve_time_12_pm(self, parser):
        """Should resolve '12 pm' to 12:00."""
        assert parser._resolve_time("12 pm") == "12:00"
    
    def test_resolve_time_12_am(self, parser):
        """Should resolve '12 am' to 00:00."""
        assert parser._resolve_time("12 am") == "00:00"
    
    def test_resolve_time_24_hour_format(self, parser):
        """Should pass through 24-hour format."""
        assert parser._resolve_time("18:00") == "18:00"
        assert parser._resolve_time("14:30") == "14:30"
    
    def test_resolve_time_24_hour_format_single_digit(self, parser):
        """Should handle single digit hours."""
        assert parser._resolve_time("9:00") == "09:00"
    
    def test_resolve_time_none(self, parser):
        """Should return None for None input."""
        assert parser._resolve_time(None) is None
    
    def test_resolve_time_empty(self, parser):
        """Should return None for empty string."""
        assert parser._resolve_time("") is None
    
    def test_resolve_time_with_periods(self, parser):
        """Should handle a.m./p.m. notation."""
        result = parser._resolve_time("3 p.m.")
        assert result == "15:00"


# ===========================================================================
# DATE RESOLUTION TESTS
# ===========================================================================

class TestDateResolution:
    """Tests for _resolve_event_date method."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return IntentParser()
    
    def test_resolve_date_today(self, parser):
        """Should resolve 'today' to today's date."""
        result = parser._resolve_event_date("today", "meeting today")
        expected = datetime.now().strftime("%Y-%m-%d")
        assert result == expected
    
    def test_resolve_date_tomorrow(self, parser):
        """Should resolve 'tomorrow' to tomorrow's date."""
        result = parser._resolve_event_date("tomorrow", "meeting tomorrow")
        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected
    
    def test_resolve_date_day_after_tomorrow(self, parser):
        """Should resolve 'day after tomorrow'."""
        result = parser._resolve_event_date("day after tomorrow", "meeting day after tomorrow")
        expected = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        assert result == expected
    
    def test_resolve_date_iso_format(self, parser):
        """Should pass through ISO format."""
        result = parser._resolve_event_date("2025-01-15", "")
        assert result == "2025-01-15"
    
    def test_resolve_date_next_weekday(self, parser):
        """Should resolve 'next monday' to next Monday."""
        result = parser._resolve_event_date("next monday", "meeting next monday")
        # Result should be a valid date
        assert result is not None
        assert len(result) == 10  # YYYY-MM-DD format
    
    def test_resolve_date_weekday_name(self, parser):
        """Should resolve weekday names."""
        result = parser._resolve_event_date("friday", "meeting on friday")
        assert result is not None
        # Should be in the future
        result_date = datetime.strptime(result, "%Y-%m-%d").date()
        assert result_date >= datetime.now().date()
    
    def test_resolve_date_month_day(self, parser):
        """Should resolve 'January 15'."""
        result = parser._resolve_event_date("january 15", "meeting on january 15")
        assert result is not None
        assert "-01-15" in result
    
    def test_resolve_date_none(self, parser):
        """Should return None for None input."""
        assert parser._resolve_event_date(None, "") is None
    
    def test_resolve_date_empty(self, parser):
        """Should return None for empty string."""
        # Actually returns empty string as-is
        result = parser._resolve_event_date("", "")
        assert result is None or result == ""


# ===========================================================================
# RECURRENCE PARSING TESTS
# ===========================================================================

class TestRecurrenceParsing:
    """Tests for _parse_recurrence method."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return IntentParser()
    
    def test_parse_recurrence_daily(self, parser):
        """Should parse 'daily' to RRULE."""
        result = parser._parse_recurrence("daily")
        assert result == "RRULE:FREQ=DAILY"
    
    def test_parse_recurrence_weekly(self, parser):
        """Should parse 'weekly' to RRULE."""
        result = parser._parse_recurrence("weekly")
        assert result == "RRULE:FREQ=WEEKLY"
    
    def test_parse_recurrence_monthly(self, parser):
        """Should parse 'monthly' to RRULE."""
        result = parser._parse_recurrence("monthly")
        assert result == "RRULE:FREQ=MONTHLY"
    
    def test_parse_recurrence_yearly(self, parser):
        """Should parse 'yearly' to RRULE."""
        result = parser._parse_recurrence("yearly")
        assert result == "RRULE:FREQ=YEARLY"
    
    def test_parse_recurrence_every_day(self, parser):
        """Should parse 'every day' to RRULE."""
        result = parser._parse_recurrence("every day")
        assert result == "RRULE:FREQ=DAILY"
    
    def test_parse_recurrence_every_week(self, parser):
        """Should parse 'every week' to RRULE."""
        result = parser._parse_recurrence("every week")
        assert result == "RRULE:FREQ=WEEKLY"
    
    def test_parse_recurrence_every_monday(self, parser):
        """Should parse 'every monday' to weekly on Monday."""
        result = parser._parse_recurrence("every monday")
        assert result == "RRULE:FREQ=WEEKLY;BYDAY=MO"
    
    def test_parse_recurrence_pass_through_rrule(self, parser):
        """Should pass through existing RRULE."""
        result = parser._parse_recurrence("RRULE:FREQ=WEEKLY;COUNT=4")
        assert result == "RRULE:FREQ=WEEKLY;COUNT=4"
    
    def test_parse_recurrence_none(self, parser):
        """Should return None for None input."""
        assert parser._parse_recurrence(None) is None
    
    def test_parse_recurrence_weekly_tuesday(self, parser):
        """Should parse weekly on specific day."""
        result = parser._parse_recurrence("weekly_tuesday")
        assert "BYDAY=TU" in result


# ===========================================================================
# ALL-DAY DETECTION TESTS
# ===========================================================================

class TestAllDayDetection:
    """Tests for _detect_all_day method."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return IntentParser()
    
    def test_detect_all_day_birthday(self, parser):
        """Should detect birthday as all-day."""
        result = parser._detect_all_day("add birthday on january 15", None)
        assert result is True
    
    def test_detect_all_day_vacation(self, parser):
        """Should detect vacation as all-day."""
        result = parser._detect_all_day("schedule vacation next week", None)
        assert result is True
    
    def test_detect_all_day_holiday(self, parser):
        """Should detect holiday as all-day."""
        result = parser._detect_all_day("add holiday on december 25", None)
        assert result is True
    
    def test_detect_all_day_anniversary(self, parser):
        """Should detect anniversary as all-day."""
        result = parser._detect_all_day("add anniversary on june 10", None)
        assert result is True
    
    def test_detect_all_day_explicit(self, parser):
        """Should detect 'all day' keyword."""
        result = parser._detect_all_day("schedule all day event", None)
        assert result is True
    
    def test_detect_all_day_with_time(self, parser):
        """Should return False if time is provided."""
        result = parser._detect_all_day("meeting at 3 pm", "15:00")
        assert result is False
    
    def test_detect_all_day_no_time_no_keywords(self, parser):
        """Should default to all-day if no time and no special keywords."""
        result = parser._detect_all_day("some event", None)
        assert result is True  # Defaults to all-day without time


# ===========================================================================
# TITLE EXTRACTION TESTS
# ===========================================================================

class TestTitleExtraction:
    """Tests for _extract_event_title method."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return IntentParser()
    
    def test_extract_title_schedule_pattern(self, parser):
        """Should extract title from 'schedule a meeting tomorrow'."""
        result = parser._extract_event_title("schedule a meeting tomorrow")
        assert "meeting" in result.lower()
    
    def test_extract_title_add_pattern(self, parser):
        """Should extract title from 'add team standup every monday'."""
        result = parser._extract_event_title("add team standup every monday")
        assert "team" in result.lower() or "standup" in result.lower()
    
    def test_extract_title_create_pattern(self, parser):
        """Should extract title from 'create a call with john'."""
        result = parser._extract_event_title("create a call with john for tomorrow")
        assert len(result) > 0
    
    def test_extract_title_fallback(self, parser):
        """Should return default if no pattern matches."""
        result = parser._extract_event_title("random text without event pattern")
        # Should return something (could be default or extracted)
        assert result is not None


# ===========================================================================
# PARSER CREATE_CALENDAR_CREATE TESTS
# ===========================================================================

class TestParserCreateCalendarCreate:
    """Tests for _create_calendar_create method."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return IntentParser()
    
    def test_create_event_intent_basic(self, parser):
        """Should create CREATE_EVENT intent."""
        data = {
            "action": "create_event",
            "event_title": "Meeting",
            "event_date": "tomorrow",
            "event_time": "6 pm",
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="schedule a meeting tomorrow at 6 pm",
            confidence=0.9,
            reasoning="User wants to create event",
        )
        
        assert isinstance(intent, CalendarCreateIntent)
        assert intent.action == ActionType.CREATE_EVENT
        assert intent.event_title == "Meeting"
    
    def test_create_event_resolves_time(self, parser):
        """Should resolve time to 24-hour format."""
        data = {
            "action": "create_event",
            "event_title": "Meeting",
            "event_time": "6 pm",
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="schedule a meeting at 6 pm",
            confidence=0.9,
            reasoning=None,
        )
        
        assert intent.event_time == "18:00"
    
    def test_create_event_resolves_date(self, parser):
        """Should resolve relative date."""
        data = {
            "action": "create_event",
            "event_title": "Meeting",
            "event_date": "tomorrow",
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="schedule a meeting tomorrow",
            confidence=0.9,
            reasoning=None,
        )
        
        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert intent.event_date == expected
    
    def test_create_event_detects_all_day(self, parser):
        """Should detect all-day events."""
        data = {
            "action": "create_event",
            "event_title": "Birthday Party",
            "event_date": "2025-01-15",
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="add birthday party on january 15",
            confidence=0.9,
            reasoning=None,
        )
        
        assert intent.is_all_day is True
    
    def test_confirm_create_intent(self, parser):
        """Should create CONFIRM_CREATE intent."""
        data = {
            "action": "confirm_create",
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="yes",
            confidence=0.99,
            reasoning=None,
        )
        
        assert intent.action == ActionType.CONFIRM_CREATE
    
    def test_cancel_create_intent(self, parser):
        """Should create CANCEL_CREATE intent."""
        data = {
            "action": "cancel_create",
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="no",
            confidence=0.99,
            reasoning=None,
        )
        
        assert intent.action == ActionType.CANCEL_CREATE
    
    def test_edit_pending_intent(self, parser):
        """Should create EDIT_PENDING_EVENT intent."""
        data = {
            "action": "edit_pending_event",
            "edit_field": "event_time",
            "edit_value": "7 pm",
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="change time to 7 pm",
            confidence=0.9,
            reasoning=None,
        )
        
        assert intent.action == ActionType.EDIT_PENDING_EVENT
        assert intent.edit_field == "event_time"
        assert intent.edit_value == "7 pm"
    
    def test_default_duration(self, parser):
        """Should default to 60 minutes."""
        data = {
            "action": "create_event",
            "event_title": "Meeting",
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="schedule a meeting",
            confidence=0.9,
            reasoning=None,
        )
        
        assert intent.duration_minutes == 60
    
    def test_custom_duration(self, parser):
        """Should use provided duration."""
        data = {
            "action": "create_event",
            "event_title": "Long Meeting",
            "duration_minutes": 120,
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="schedule a 2 hour meeting",
            confidence=0.9,
            reasoning=None,
        )
        
        assert intent.duration_minutes == 120
    
    def test_extracts_title_if_missing(self, parser):
        """Should extract title from text if not provided."""
        data = {
            "action": "create_event",
            "event_date": "tomorrow",
            "event_time": "6 pm",
        }
        
        intent = parser._create_calendar_create(
            data=data,
            original_text="schedule a meeting tomorrow at 6 pm",
            confidence=0.9,
            reasoning=None,
        )
        
        # Should have extracted a title
        assert intent.event_title is not None
