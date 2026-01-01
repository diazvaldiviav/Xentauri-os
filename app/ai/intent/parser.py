"""
Intent Parser - Extracts structured intents from natural language.

This is the core NLU (Natural Language Understanding) component.
It uses Gemini Flash to parse user requests into structured intents.

The parser:
1. Takes raw text input ("Turn on the living room TV")
2. Calls Gemini with intent extraction prompts
3. Parses JSON response into typed Intent objects
4. Returns structured data ready for device mapping

Why Gemini Flash?
================
- Fast: <1s response time for most requests
- Cheap: ~$0.00001 per request
- Accurate: Excellent at structured extraction
- JSON mode: Built-in JSON output format
"""

import json
import logging
import time
import uuid
from typing import Optional, Dict, Any, Union

from app.ai.providers import gemini_provider, AIResponse
from app.ai.prompts.intent_prompts import (
    INTENT_SYSTEM_PROMPT,
    INTENT_EXTRACTION_PROMPT,
)
from app.ai.intent.schemas import (
    Intent,
    IntentType,
    ActionType,
    DeviceCommand,
    DeviceQuery,
    SystemQuery,
    CalendarQueryIntent,
    CalendarCreateIntent,
    CalendarEditIntent,
    DocQueryIntent,
    DisplayContentIntent,
    ConversationIntent,
    ParsedCommand,
    SequentialAction,  # Sprint 4.0.3: Multi-action support
)

logger = logging.getLogger("jarvis.ai.intent")


class IntentParser:
    """
    Parses natural language into structured intents.
    
    This class is responsible for:
    - Calling the LLM to extract intent
    - Parsing JSON responses
    - Creating typed Intent objects
    - Handling errors gracefully
    
    Usage:
        parser = IntentParser()
        intent = await parser.parse("Turn on the living room TV")
        
        if isinstance(intent, DeviceCommand):
            print(f"Command: {intent.action} on {intent.device_name}")
    """
    
    def __init__(self):
        """Initialize the parser with Gemini provider."""
        self.provider = gemini_provider
        logger.info("Intent parser initialized")
    
    async def parse(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Intent:
        """
        Parse natural language text into a structured intent.
        
        Args:
            text: The user's natural language request
            context: Optional context (available devices, user info, pending operations)
            
        Returns:
            Typed Intent object (DeviceCommand, DeviceQuery, etc.)
        """
        start_time = time.time()
        logger.info(f"Parsing intent: {text[:50]}...")
        
        # Build context string with devices, pending operations, conversation history, and generated content
        # Sprint 4.2 FIX: Include conversation context for memory-aware parsing
        context_parts = []
        if context:
            # Add device context
            if "devices" in context:
                device_names = [d.get("name", "Unknown") for d in context["devices"]]
                context_parts.append(f"Available devices: {', '.join(device_names)}")
            
            # Add pending operation context (critical for "yes"/"no" disambiguation)
            if "pending_operation" in context and context["pending_operation"]:
                pending_op = context["pending_operation"]
                pending_lines = []
                
                if pending_op.get("has_pending_create"):
                    pending_lines.append("has_pending_create: true")
                    if pending_op.get("pending_create_title"):
                        pending_lines.append(f"pending_event: {pending_op['pending_create_title']}")
                
                if pending_op.get("has_pending_edit"):
                    pending_lines.append("has_pending_edit: true")
                    if pending_op.get("pending_edit_event"):
                        pending_lines.append(f"editing_event: {pending_op['pending_edit_event']}")
                
                if pending_op.get("has_pending_delete"):
                    pending_lines.append("has_pending_delete: true")
                
                if pending_op.get("pending_op_type"):
                    pending_lines.append(f"pending_op_type: {pending_op['pending_op_type']}")
                
                if pending_op.get("pending_op_age_seconds") is not None:
                    pending_lines.append(f"pending_op_age_seconds: {pending_op['pending_op_age_seconds']}")
                
                if pending_lines:
                    context_parts.append("Pending operation state:\n" + "\n".join(pending_lines))
            
            # Sprint 4.2: Add conversation history context
            if "conversation_context" in context and context["conversation_context"]:
                conv_ctx = context["conversation_context"]
                conv_lines = []
                
                # Add recent conversation if available
                if conv_ctx.get("conversation"):
                    conv = conv_ctx["conversation"]
                    if conv.get("last_user") and conv.get("is_recent"):
                        conv_lines.append(f"Last user message: {conv['last_user']}")
                    if conv.get("last_assistant") and conv.get("is_recent"):
                        conv_lines.append(f"Last assistant response: {conv['last_assistant'][:150]}...")
                    if conv.get("last_intent"):
                        conv_lines.append(f"Last intent type: {conv['last_intent']}")
                
                if conv_lines:
                    context_parts.append("Recent conversation:\n" + "\n".join(conv_lines))
            
            # Sprint 4.2: Add generated content context (CRITICAL for "show that note" references)
            if "generated_content" in context and context["generated_content"]:
                gen_content = context["generated_content"]
                from datetime import datetime, timezone
                
                # Calculate how long ago the content was generated
                timestamp = gen_content.get("timestamp")
                if timestamp:
                    if isinstance(timestamp, datetime):
                        elapsed = (datetime.now(timezone.utc) - timestamp).total_seconds()
                    else:
                        elapsed = 0
                    minutes_ago = int(elapsed / 60)
                else:
                    minutes_ago = 0
                
                content_preview = gen_content.get("content", "")[:200]
                content_type = gen_content.get("type", "content")
                content_title = gen_content.get("title", "Untitled")
                
                gen_context = f"""RECENTLY GENERATED CONTENT IN MEMORY ({minutes_ago} min ago):
Type: {content_type}
Title: {content_title}
Preview: {content_preview}...

IMPORTANT: If user references "that note", "the template", "what you created", "ese informe", "esa nota" etc., 
this refers to the content above (in WORKING MEMORY), NOT Google Docs.
Use DISPLAY_CONTENT intent to show this content, NOT DOC_QUERY."""
                
                context_parts.append(gen_context)
        
        context_str = ""
        if context_parts:
            context_str = "\n\n" + "\n\n".join(context_parts)
        
        # Build the prompt
        prompt = INTENT_EXTRACTION_PROMPT.format(
            request=text,
            context=context_str,
        )
        
        # Call Gemini for intent extraction
        response = await self.provider.generate_json(
            prompt=prompt,
            system_prompt=INTENT_SYSTEM_PROMPT,
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        if not response.success:
            logger.warning(f"Intent parsing failed: {response.error}")
            return self._create_unknown_intent(text, response.error)
        
        # Parse the JSON response into an Intent object
        try:
            intent_data = json.loads(response.content)
            intent = self._create_intent(intent_data, text)
            logger.info(f"Parsed intent in {processing_time:.0f}ms: {intent.intent_type}")
            return intent

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse intent JSON: {e}")
            logger.debug(f"Raw Gemini response: {response.content[:500]}...")

            # Sprint 4.3.1: Try to clean common JSON errors
            try:
                import re
                cleaned_content = response.content

                # Remove trailing commas
                cleaned_content = re.sub(r',(\s*[}\]])', r'\1', cleaned_content)

                # Fix unterminated strings - add closing quotes before newlines followed by }
                cleaned_content = re.sub(r'(["\'])\s*\n\s*}', r'\1}', cleaned_content)

                # Try parsing again
                intent_data = json.loads(cleaned_content)
                intent = self._create_intent(intent_data, text)
                logger.info(f"Recovered from JSON error with cleanup")
                return intent
            except Exception as retry_error:
                logger.error(f"JSON cleanup failed: {retry_error}")
                return self._create_unknown_intent(text, str(e))

        except Exception as e:
            logger.error(f"Intent creation failed: {e}")
            return self._create_unknown_intent(text, str(e))
    
    def _create_intent(self, data: Dict[str, Any], original_text: str) -> Intent:
        """
        Create a typed Intent object from parsed JSON data.
        
        Routes to the appropriate Intent subclass based on intent_type.
        """
        intent_type = data.get("intent_type", "unknown").lower()
        confidence = float(data.get("confidence", 0.5))
        reasoning = data.get("reasoning")
        
        # Route to appropriate intent type
        if intent_type == "device_command":
            return self._create_device_command(data, original_text, confidence, reasoning)
        
        elif intent_type == "device_query":
            return self._create_device_query(data, original_text, confidence, reasoning)
        
        elif intent_type == "system_query":
            return self._create_system_query(data, original_text, confidence, reasoning)
        
        elif intent_type == "calendar_query":
            return self._create_calendar_query(data, original_text, confidence, reasoning)
        
        elif intent_type == "calendar_create":
            return self._create_calendar_create(data, original_text, confidence, reasoning)
        
        elif intent_type == "calendar_edit":
            return self._create_calendar_edit(data, original_text, confidence, reasoning)
        
        elif intent_type == "doc_query":
            return self._create_doc_query(data, original_text, confidence, reasoning)
        
        elif intent_type == "display_content":
            return self._create_display_content_intent(data, original_text, confidence, reasoning)
        
        elif intent_type == "conversation":
            return self._create_conversation_intent(data, original_text, confidence, reasoning)
        
        else:
            return self._create_unknown_intent(original_text, f"Unknown intent type: {intent_type}")
    
    def _create_device_command(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> DeviceCommand:
        """Create a DeviceCommand intent."""
        device_name = data.get("device_name", "unknown device")
        action_str = data.get("action", "").lower()
        parameters = data.get("parameters") or {}
        
        # Map action string to ActionType
        action = self._map_action(action_str)
        
        # Resolve relative dates in parameters for calendar commands
        if action_str in ("show_calendar", "show_content") and parameters:
            parameters = self._resolve_parameters_dates(parameters, original_text)
        
        # Sprint 4.0.3: Extract sequential actions for multi-action requests
        sequential_actions = self._extract_sequential_actions(data, original_text)
        
        return DeviceCommand(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            device_name=device_name,
            action=action,
            parameters=parameters if parameters else None,
            sequential_actions=sequential_actions,
        )
    
    def _resolve_parameters_dates(self, parameters: Dict, original_text: str) -> Dict:
        """
        Resolve relative date references in command parameters.
        
        AI models don't know the current date, so "today" might be returned as
        an incorrect date. We extract it from the text and resolve it properly.
        """
        from datetime import datetime, timedelta
        
        text_lower = original_text.lower()
        today = datetime.now()

        # Sprint 5.1.1: Added Spanish support for relative dates
        # If user said "today"/"hoy", use actual today's date
        if "today" in text_lower or "hoy" in text_lower:
            parameters["date"] = today.strftime("%Y-%m-%d")
        elif "tomorrow" in text_lower or "mañana" in text_lower:
            tomorrow = today + timedelta(days=1)
            parameters["date"] = tomorrow.strftime("%Y-%m-%d")
        elif "yesterday" in text_lower or "ayer" in text_lower:
            yesterday = today - timedelta(days=1)
            parameters["date"] = yesterday.strftime("%Y-%m-%d")
        elif "date" in parameters:
            # Resolve if the AI returned relative terms (EN + ES)
            date_value = str(parameters.get("date", "")).lower()
            if date_value in ("today", "hoy"):
                parameters["date"] = today.strftime("%Y-%m-%d")
            elif date_value in ("tomorrow", "mañana"):
                tomorrow = today + timedelta(days=1)
                parameters["date"] = tomorrow.strftime("%Y-%m-%d")
            elif date_value in ("yesterday", "ayer"):
                yesterday = today - timedelta(days=1)
                parameters["date"] = yesterday.strftime("%Y-%m-%d")
        
        return parameters
    
    def _extract_sequential_actions(
        self, data: Dict[str, Any], original_text: str
    ) -> list[SequentialAction]:
        """
        Extract sequential actions from parsed AI response.
        
        Sprint 4.0.3: Multi-action support allows users to chain actions like
        "clear the screen AND show my calendar".
        
        The AI returns a sequential_actions array that we convert to SequentialAction objects.
        """
        raw_actions = data.get("sequential_actions", [])
        
        if not raw_actions or not isinstance(raw_actions, list):
            return []
        
        sequential_actions = []
        for action_data in raw_actions:
            if not isinstance(action_data, dict):
                logger.warning(f"Skipping invalid sequential action: {action_data}")
                continue
            
            action_str = action_data.get("action", "")
            if not action_str:
                logger.warning(f"Skipping sequential action without 'action' field: {action_data}")
                continue
            
            # Resolve parameters dates if needed
            params = action_data.get("parameters")
            if params and action_str in ("show_calendar", "show_content"):
                params = self._resolve_parameters_dates(params, original_text)
            
            seq_action = SequentialAction(
                action=action_str,
                device_name=action_data.get("device_name"),
                parameters=params,
                content_type=action_data.get("content_type"),
            )
            sequential_actions.append(seq_action)
            logger.debug(f"Extracted sequential action: {seq_action.action} → {seq_action.device_name}")
        
        if sequential_actions:
            logger.info(f"Multi-action request detected: {len(sequential_actions)} sequential actions")
        
        return sequential_actions
    
    def _create_device_query(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> DeviceQuery:
        """Create a DeviceQuery intent."""
        device_name = data.get("device_name") or "unknown device"
        action_str = data.get("action", "status").lower()
        action = self._map_action(action_str)
        
        return DeviceQuery(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            device_name=device_name,
            action=action,
        )
    
    def _create_system_query(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> SystemQuery:
        """Create a SystemQuery intent."""
        action_str = data.get("action", "help").lower()
        action = self._map_action(action_str)
        parameters = data.get("parameters")
        
        return SystemQuery(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            action=action,
            parameters=parameters,
        )
    
    def _create_conversation_intent(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> ConversationIntent:
        """Create a ConversationIntent."""
        action_str = data.get("action", "").lower()
        action = self._map_action(action_str) if action_str else None
        
        return ConversationIntent(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            action=action,
        )
    
    def _create_display_content_intent(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> DisplayContentIntent:
        """
        Create a DisplayContentIntent for scene-based display requests.
        
        Sprint 4.0: Handles requests for custom layouts like
        "calendar on the left with clock in the corner".
        """
        # Extract classification fields
        info_type = data.get("info_type", "calendar")
        output_type = data.get("output_type", "display")
        layout_type = data.get("layout_type", "default")
        
        # Extract layout hints (list of strings like "calendar left", "clock corner")
        layout_hints = data.get("layout_hints", [])
        if isinstance(layout_hints, str):
            # Handle single hint as string
            layout_hints = [layout_hints] if layout_hints else []
        
        # Extract target device if specified
        device_name = data.get("device_name")
        
        return DisplayContentIntent(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            info_type=info_type,
            output_type=output_type,
            layout_type=layout_type,
            layout_hints=layout_hints,
            device_name=device_name,
        )

    def _create_calendar_query(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> CalendarQueryIntent:
        """Create a CalendarQueryIntent for calendar data questions."""
        action_str = data.get("action", "count_events").lower()
        action = self._map_action(action_str)
        
        # Extract date_range and search_term
        date_range = data.get("date_range")
        search_term = data.get("search_term")
        
        # Resolve relative dates to actual dates
        date_range = self._resolve_date_range(date_range, original_text)
        
        # Fallback: extract search_term from original text for find_event
        if not search_term and action_str == "find_event":
            search_term = self._extract_search_term_from_text(original_text)
        
        return CalendarQueryIntent(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            action=action,
            date_range=date_range,
            search_term=search_term,
        )
    
    def _create_calendar_create(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> CalendarCreateIntent:
        """
        Create a CalendarCreateIntent for calendar event creation.
        
        Sprint 3.8: Handles create_event, confirm_create, cancel_create, edit_pending_event actions.
        """
        action_str = data.get("action", "create_event").lower()
        action = self._map_action(action_str)
        
        # Extract event details
        event_title = data.get("event_title")
        event_date = data.get("event_date")
        event_time = data.get("event_time")
        duration_minutes = data.get("duration_minutes", 60)
        is_all_day = data.get("is_all_day", False)
        location = data.get("location")
        recurrence = data.get("recurrence")
        # Sprint 5.1.1: Extract doc_url for document association
        doc_url = data.get("doc_url")
        
        # Extract edit details (for edit_pending_event action)
        edit_field = data.get("edit_field")
        edit_value = data.get("edit_value")
        
        # Resolve event_time to 24-hour format
        if event_time:
            event_time = self._resolve_time(event_time)
        
        # Resolve event_date to ISO format
        if event_date:
            event_date = self._resolve_event_date(event_date, original_text)
        
        # Parse recurrence pattern
        if recurrence:
            recurrence = self._parse_recurrence(recurrence)
        
        # Detect all-day from context
        if not is_all_day and event_date and not event_time:
            is_all_day = self._detect_all_day(original_text, event_time)
        
        # Default title if not provided
        if action_str == "create_event" and not event_title:
            event_title = self._extract_event_title(original_text)
        
        # Ensure duration is an int
        try:
            duration_minutes = int(duration_minutes) if duration_minutes else 60
        except (ValueError, TypeError):
            duration_minutes = 60
        
        return CalendarCreateIntent(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            action=action,
            event_title=event_title,
            event_date=event_date,
            event_time=event_time,
            duration_minutes=duration_minutes,
            is_all_day=is_all_day,
            location=location,
            recurrence=recurrence,
            edit_field=edit_field,
            edit_value=edit_value,
            doc_url=doc_url,  # Sprint 5.1.1
        )
    
    def _create_calendar_edit(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> CalendarEditIntent:
        """
        Create a CalendarEditIntent for editing/deleting existing events.
        
        Sprint 3.9: Handles edit_existing_event, delete_existing_event, select_event,
        confirm_edit, confirm_delete, cancel_edit actions.
        """
        action_str = data.get("action", "edit_existing_event").lower()
        action = self._map_action(action_str)
        
        # Extract search criteria
        search_term = data.get("search_term")
        date_filter = data.get("date_filter")
        
        # Extract event selection
        selection_index = data.get("selection_index")
        event_id = data.get("event_id")
        
        # Extract changes for edit operation
        changes = data.get("changes")
        
        # Parse selection_index from natural language
        if not selection_index:
            selection_index = self._detect_selection_index(original_text)
        
        # Ensure selection_index is an int if present
        if selection_index:
            try:
                selection_index = int(selection_index)
            except (ValueError, TypeError):
                selection_index = None
        
        # Resolve date filter to ISO format if needed
        if date_filter:
            date_filter = self._resolve_event_date(date_filter, original_text)
        
        # Process changes - resolve time values
        if changes:
            changes = self._process_edit_changes(changes, original_text)
        
        return CalendarEditIntent(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            action=action,
            search_term=search_term,
            date_filter=date_filter,
            selection_index=selection_index,
            event_id=event_id,
            changes=changes,
        )
    
    def _create_doc_query(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> DocQueryIntent:
        """
        Create a DocQueryIntent for document-related queries.
        
        Sprint 3.9: Handles read_doc, link_doc, open_doc, summarize_meeting_doc actions.
        Sprint 4.0.2: Supports compound intents with also_display flag.
        """
        action_str = data.get("action", "summarize_meeting_doc").lower()
        action = self._map_action(action_str)
        
        # Extract document identification
        doc_url = data.get("doc_url")
        doc_id = data.get("doc_id")
        
        # Extract meeting reference
        meeting_search = data.get("meeting_search")
        meeting_time = data.get("meeting_time")
        
        # Extract query details
        question = data.get("question")
        device_name = data.get("device_name")
        
        # Sprint 4.0.2: Compound intent support
        also_display = data.get("also_display", False)
        display_device = data.get("display_device")
        
        # Try to extract doc ID from URL if present
        if doc_url and not doc_id:
            doc_id = self._extract_google_doc_id(doc_url)
        
        # Also check the original text for doc URLs
        if not doc_id:
            doc_id = self._extract_google_doc_id(original_text)
        
        return DocQueryIntent(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            action=action,
            doc_url=doc_url,
            doc_id=doc_id,
            meeting_search=meeting_search,
            meeting_time=meeting_time,
            question=question,
            device_name=device_name,
            also_display=also_display,
            display_device=display_device,
        )
    
    def _extract_google_doc_id(self, text: str) -> Optional[str]:
        """
        Extract a Google Doc ID from text containing a URL.
        
        Supports multiple URL formats:
        - https://docs.google.com/document/d/{docId}/edit
        - https://docs.google.com/document/d/{docId}/view
        - https://docs.google.com/open?id={docId}
        
        Args:
            text: Text that might contain a Google Doc URL
        
        Returns:
            Document ID if found, None otherwise
        """
        import re
        
        if not text:
            return None
        
        # Standard document URL pattern
        match = re.search(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", text)
        if match:
            return match.group(1)
        
        # Open URL pattern
        match = re.search(r"docs\.google\.com/open\?id=([a-zA-Z0-9_-]+)", text)
        if match:
            return match.group(1)
        
        return None
    
    def _detect_selection_index(self, text: str) -> Optional[int]:
        """
        Detect event selection from natural language.
        
        Examples:
            "the first one" → 1
            "number 2" → 2
            "the second" → 2
            "3" → 3
        """
        import re
        
        text = text.lower().strip()
        
        # Direct number
        if text.isdigit():
            return int(text)
        
        # "the first one", "first one", "the first"
        ordinal_map = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
            "1st": 1,
            "2nd": 2,
            "3rd": 3,
            "4th": 4,
            "5th": 5,
        }
        
        for ordinal, num in ordinal_map.items():
            if ordinal in text:
                return num
        
        # "number 2", "option 3"
        num_match = re.search(r"(?:number|option|choice)\s*(\d+)", text)
        if num_match:
            return int(num_match.group(1))
        
        return None
    
    def _process_edit_changes(self, changes: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        """
        Process and normalize edit changes.
        
        Resolves relative times and dates to proper formats.
        """
        processed = {}
        
        for field, value in changes.items():
            if value is None:
                continue
            
            if field in ("start_datetime", "end_datetime"):
                # Could be "3pm", "15:00", or "tomorrow at 3pm"
                time_value = self._resolve_time(str(value))
                if time_value:
                    processed[field] = time_value
                else:
                    # Might be a date-time string
                    processed[field] = value
            elif field in ("start_date", "end_date"):
                date_value = self._resolve_event_date(str(value), original_text)
                if date_value:
                    processed[field] = date_value
                else:
                    processed[field] = value
            else:
                processed[field] = value
        
        return processed
    
    def _resolve_time(self, time_str: str) -> Optional[str]:
        """
        Convert natural time to 24-hour format.
        
        Examples:
            "6 pm" → "18:00"
            "10 am" → "10:00"
            "2:30 pm" → "14:30"
            "noon" → "12:00"
            "midnight" → "00:00"
            "18:00" → "18:00" (pass through)
        """
        import re
        
        if not time_str:
            return None
        
        time_str = time_str.lower().strip()
        
        # Handle special cases
        if time_str == "noon":
            return "12:00"
        if time_str == "midnight":
            return "00:00"
        
        # Already in 24-hour format (e.g., "18:00")
        if re.match(r"^\d{1,2}:\d{2}$", time_str):
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
            return f"{hour:02d}:{minute:02d}"
        
        # Parse AM/PM format
        am_pm_match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?", time_str)
        if am_pm_match:
            hour = int(am_pm_match.group(1))
            minute = int(am_pm_match.group(2)) if am_pm_match.group(2) else 0
            am_pm = am_pm_match.group(3)
            
            if am_pm and "p" in am_pm.lower() and hour != 12:
                hour += 12
            elif am_pm and "a" in am_pm.lower() and hour == 12:
                hour = 0
            
            return f"{hour:02d}:{minute:02d}"
        
        return time_str  # Return as-is if can't parse
    
    def _resolve_event_date(self, date_str: str, original_text: str) -> Optional[str]:
        """
        Convert natural date to ISO format (YYYY-MM-DD).
        
        Examples:
            "tomorrow" → "2025-12-17"
            "next Monday" → next Monday's date
            "January 15" → "2025-01-15" (or 2026 if past)
            "2025-01-15" → "2025-01-15" (pass through)
        """
        import re
        from datetime import datetime, timedelta
        
        if not date_str:
            return None
        
        date_str = date_str.lower().strip()
        today = datetime.now()
        original_lower = original_text.lower() if original_text else ""

        # Sprint 5.1.1: Check original_text FIRST for relative dates
        # AI may return wrong ISO date (doesn't know current date)
        # If user said "hoy/today", use actual today regardless of AI's date
        if any(word in original_lower for word in ("hoy", "today")):
            return today.strftime("%Y-%m-%d")
        if any(word in original_lower for word in ("mañana", "tomorrow")):
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        if any(word in original_lower for word in ("pasado mañana", "day after tomorrow")):
            return (today + timedelta(days=2)).strftime("%Y-%m-%d")
        if any(word in original_lower for word in ("ayer", "yesterday")):
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")

        # "la semana que viene" / "next week" → next Monday
        if any(phrase in original_lower for phrase in (
            "semana que viene", "próxima semana", "proxima semana", "next week"
        )):
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7  # If today is Monday, go to next Monday
            return (today + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")

        # Already ISO format - but validate year (LLM may return stale year from training)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            try:
                parsed = datetime.strptime(date_str, "%Y-%m-%d")
                # If date is in the past, adjust to next occurrence
                if parsed.date() < today.date():
                    # Keep month/day, use next year
                    parsed = parsed.replace(year=today.year)
                    if parsed.date() < today.date():
                        parsed = parsed.replace(year=today.year + 1)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                return date_str

        # Relative dates from date_str (fallback)
        if date_str in ("today", "hoy"):
            return today.strftime("%Y-%m-%d")
        if date_str in ("tomorrow", "mañana"):
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        if date_str in ("day after tomorrow", "pasado mañana"):
            return (today + timedelta(days=2)).strftime("%Y-%m-%d")
        if date_str in ("yesterday", "ayer"):
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")

        # "next X" patterns (EN + ES)
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
            "lunes": 0, "martes": 1, "miércoles": 2, "jueves": 3,
            "viernes": 4, "sábado": 5, "domingo": 6
        }
        next_match = re.match(r"next\s+(\w+)", date_str)
        if next_match:
            day_name = next_match.group(1)
            if day_name in weekdays:
                target_weekday = weekdays[day_name]
                days_ahead = target_weekday - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        # Just weekday name (e.g., "monday")
        for day_name, weekday in weekdays.items():
            if day_name in date_str:
                days_ahead = weekday - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        # Month day format (e.g., "January 15", "15 de enero") - EN + ES
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
            "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
            "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
        }
        for month_name, month_num in months.items():
            # English format: "December 31"
            month_match = re.search(rf"{month_name}\s+(\d{{1,2}})", date_str)
            # Spanish format: "31 de diciembre"
            if not month_match:
                month_match = re.search(rf"(\d{{1,2}})\s+de\s+{month_name}", date_str)
            if month_match:
                day = int(month_match.group(1))
                year = today.year
                # If the date has passed this year, use next year
                try:
                    target_date = datetime(year, month_num, day)
                    if target_date < today:
                        target_date = datetime(year + 1, month_num, day)
                    return target_date.strftime("%Y-%m-%d")
                except ValueError:
                    pass
        
        return date_str  # Return as-is if can't parse
    
    def _parse_recurrence(self, recurrence_str: str) -> Optional[str]:
        """
        Parse recurrence pattern to RRULE format.
        
        Examples:
            "daily" → "RRULE:FREQ=DAILY"
            "weekly" → "RRULE:FREQ=WEEKLY"
            "weekly_monday" → "RRULE:FREQ=WEEKLY;BYDAY=MO"
            "monthly" → "RRULE:FREQ=MONTHLY"
            "RRULE:..." → pass through
        """
        if not recurrence_str:
            return None
        
        recurrence_str = recurrence_str.lower().strip()
        
        # Already an RRULE
        if recurrence_str.startswith("rrule:"):
            return recurrence_str.upper()
        
        # Simple patterns
        patterns = {
            "daily": "RRULE:FREQ=DAILY",
            "weekly": "RRULE:FREQ=WEEKLY",
            "monthly": "RRULE:FREQ=MONTHLY",
            "yearly": "RRULE:FREQ=YEARLY",
            "every day": "RRULE:FREQ=DAILY",
            "every week": "RRULE:FREQ=WEEKLY",
            "every month": "RRULE:FREQ=MONTHLY",
        }
        
        if recurrence_str in patterns:
            return patterns[recurrence_str]
        
        # Weekly with specific days
        weekday_codes = {
            "monday": "MO", "tuesday": "TU", "wednesday": "WE",
            "thursday": "TH", "friday": "FR", "saturday": "SA", "sunday": "SU"
        }
        
        for day_name, code in weekday_codes.items():
            if day_name in recurrence_str:
                return f"RRULE:FREQ=WEEKLY;BYDAY={code}"
        
        # Check for "weekly_dayname" format (from LLM)
        for day_name, code in weekday_codes.items():
            if f"weekly_{day_name}" in recurrence_str:
                return f"RRULE:FREQ=WEEKLY;BYDAY={code}"
        
        return recurrence_str  # Return as-is if can't parse
    
    def _detect_all_day(self, text: str, event_time: Optional[str]) -> bool:
        """
        Detect if event should be all-day.
        
        Returns True if:
            - No time specified
            - Keywords like "birthday", "vacation", "holiday", "anniversary"
        """
        if event_time:
            return False
        
        all_day_keywords = [
            "birthday", "vacation", "holiday", "anniversary",
            "all day", "all-day", "entire day"
        ]
        
        text_lower = text.lower()
        for keyword in all_day_keywords:
            if keyword in text_lower:
                return True
        
        return False  # Don't assume all-day; let the flow ask for time
    
    def _extract_event_title(self, text: str) -> str:
        """
        Extract a default event title from the text if not provided.
        
        Examples:
            "schedule a meeting tomorrow" → "Meeting"
            "add team standup every monday" → "Team Standup"
        """
        import re
        
        text_lower = text.lower()
        
        # Common patterns to extract titles
        patterns = [
            r"schedule\s+(?:a\s+)?(.+?)\s+(?:on|for|at|tomorrow|today|next)",
            r"add\s+(?:a\s+)?(.+?)\s+(?:on|for|at|tomorrow|today|next|every)",
            r"create\s+(?:a\s+)?(.+?)\s+(?:on|for|at|tomorrow|today|next)",
            r"book\s+(?:a\s+)?(.+?)\s+(?:on|for|at|tomorrow|today|next)",
            r"set up\s+(?:a\s+)?(.+?)\s+(?:on|for|at|tomorrow|today|next)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                title = match.group(1).strip()
                # Clean up and capitalize
                title = re.sub(r"\s+", " ", title)
                return title.title()
        
        # Default fallback
        return "Event"
    
    def _resolve_date_range(self, date_range: Optional[str], original_text: str) -> Optional[str]:
        """
        Resolve relative date references to actual ISO dates.
        
        - "today" → "2025-12-12" (today's date)
        - "tomorrow" → "2025-12-13"
        - "this_week" kept as-is for week range
        - Already ISO date passed through
        """
        from datetime import datetime, timedelta
        
        text_lower = original_text.lower()
        today = datetime.now()
        
        # If date_range is already set, use it but resolve relative terms
        if date_range:
            date_range_lower = date_range.lower()
            if date_range_lower in ("today", "hoy"):
                return today.strftime("%Y-%m-%d")
            elif date_range_lower in ("tomorrow", "mañana"):
                tomorrow = today + timedelta(days=1)
                return tomorrow.strftime("%Y-%m-%d")
            # Keep "this_week" as-is for range queries
            return date_range

        # Try to extract from original text if not set (EN + ES)
        # Sprint 5.1.1: Added Spanish support
        if "today" in text_lower or "hoy" in text_lower:
            return today.strftime("%Y-%m-%d")
        elif "tomorrow" in text_lower or "mañana" in text_lower:
            tomorrow = today + timedelta(days=1)
            return tomorrow.strftime("%Y-%m-%d")
        elif "this week" in text_lower or "esta semana" in text_lower:
            return "this_week"
        
        return None
    
    def _extract_search_term_from_text(self, original_text: str) -> Optional[str]:
        """
        Extract search term from questions like "when is my birthday?"
        
        Patterns:
        - "when is my X?" → X
        - "when is the X?" → X
        - "what's my next X?" → X
        - "do I have any X?" → X
        """
        import re
        
        text_lower = original_text.lower().strip()
        
        # Remove question mark for easier matching
        text_lower = text_lower.rstrip("?").strip()
        
        # Pattern: "when is my X" or "when is the X"
        # Sprint 5.1.1: Added Spanish patterns
        patterns = [
            # English patterns
            r"when is (?:my|the) (.+)",
            r"when'?s (?:my|the) (.+)",
            r"what(?:'s| is) (?:my|the) next (.+)",
            r"do i have (?:any|a) (.+)",
            r"find (?:my|the) (.+)",
            # Spanish patterns
            r"cuando es (?:mi|el|la) (.+)",
            r"cuándo es (?:mi|el|la) (.+)",
            r"busca (?:mi|el|la|el evento|la cita) (.+)",
            r"buscar (?:el evento|la cita)? ?(.+)",
            r"tengo (?:algún?a?|un|una) (.+)",
            r"encuentra (?:mi|el|la) (.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                term = match.group(1).strip()
                # Clean up time/date suffixes using word boundaries (EN + ES)
                term = re.sub(r"\s+(?:today|tomorrow|this week|next week|on|in|at|for|hoy|mañana|esta semana|en|para)\b.*$", "", term)
                if term:
                    return term
        
        return None
    
    def _create_unknown_intent(
        self,
        original_text: str,
        error: Optional[str] = None,
    ) -> Intent:
        """Create an unknown intent for failed parsing."""
        return Intent(
            intent_type=IntentType.UNKNOWN,
            confidence=0.0,
            original_text=original_text,
            reasoning=f"Failed to parse: {error}" if error else "Unknown intent",
        )
    
    def _map_action(self, action_str: str) -> ActionType:
        """Map action string to ActionType enum."""
        action_map = {
            # Power actions
            "power_on": ActionType.POWER_ON,
            "power_off": ActionType.POWER_OFF,
            # Input actions
            "set_input": ActionType.SET_INPUT,
            # Volume actions
            "volume_up": ActionType.VOLUME_UP,
            "volume_down": ActionType.VOLUME_DOWN,
            "volume_set": ActionType.VOLUME_SET,
            "mute": ActionType.MUTE,
            "unmute": ActionType.UNMUTE,
            # Content display actions (Sprint 3.5)
            "show_calendar": ActionType.SHOW_CALENDAR,
            "show_content": ActionType.SHOW_CONTENT,
            "clear_content": ActionType.CLEAR_CONTENT,
            # Query actions
            "status": ActionType.STATUS,
            "capabilities": ActionType.CAPABILITIES,
            "is_online": ActionType.IS_ONLINE,
            # System actions
            "list_devices": ActionType.LIST_DEVICES,
            "help": ActionType.HELP,
            # Conversation actions
            "greeting": ActionType.GREETING,
            "thanks": ActionType.THANKS,
            "question": ActionType.QUESTION,
            # Calendar query actions (Sprint 3.8)
            "count_events": ActionType.COUNT_EVENTS,
            "next_event": ActionType.NEXT_EVENT,
            "list_events": ActionType.LIST_EVENTS,
            "find_event": ActionType.FIND_EVENT,
            # Calendar create actions (Sprint 3.8)
            "create_event": ActionType.CREATE_EVENT,
            "confirm_create": ActionType.CONFIRM_CREATE,
            "cancel_create": ActionType.CANCEL_CREATE,
            "edit_pending_event": ActionType.EDIT_PENDING_EVENT,
            # Calendar edit/delete actions (Sprint 3.9)
            "edit_existing_event": ActionType.EDIT_EXISTING_EVENT,
            "delete_existing_event": ActionType.DELETE_EXISTING_EVENT,
            "select_event": ActionType.SELECT_EVENT,
            "confirm_edit": ActionType.CONFIRM_EDIT,
            "confirm_delete": ActionType.CONFIRM_DELETE,
            "cancel_edit": ActionType.CANCEL_EDIT,
            # Document actions (Sprint 3.9)
            "read_doc": ActionType.READ_DOC,
            "link_doc": ActionType.LINK_DOC,
            "open_doc": ActionType.OPEN_DOC,
            "summarize_meeting_doc": ActionType.SUMMARIZE_MEETING_DOC,
            "create_event_from_doc": ActionType.CREATE_EVENT_FROM_DOC,
            # Display Content actions (Sprint 4.0 - Scene Graph)
            "display_scene": ActionType.DISPLAY_SCENE,
            "refresh_display": ActionType.REFRESH_DISPLAY,
        }
        return action_map.get(action_str, ActionType.STATUS)
    
    async def create_parsed_command(
        self,
        text: str,
        user_id: Optional[uuid.UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ParsedCommand:
        """
        Full processing: parse intent and create a ParsedCommand.
        
        This is a convenience method that combines parsing and
        creates a ParsedCommand ready for execution.
        
        Args:
            text: User's natural language request
            user_id: Optional user UUID
            context: Optional context with devices, etc.
            
        Returns:
            ParsedCommand with intent and execution readiness
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        # Parse the intent
        intent = await self.parse(text, context)
        
        processing_time = (time.time() - start_time) * 1000
        
        # Create ParsedCommand based on intent type
        parsed = ParsedCommand(
            request_id=request_id,
            user_id=user_id,
            intent=intent,
            ai_provider="gemini",
            processing_time_ms=processing_time,
        )
        
        # For device commands, extract additional info
        if isinstance(intent, DeviceCommand):
            parsed.device_name = intent.device_name
            parsed.action = intent.action.value if intent.action else None
            parsed.parameters = intent.parameters
            # can_execute will be set after device mapping
            
        elif isinstance(intent, DeviceQuery):
            parsed.device_name = intent.device_name
            parsed.action = intent.action.value if intent.action else None
            
        elif isinstance(intent, SystemQuery):
            parsed.action = intent.action.value if intent.action else None
            parsed.parameters = intent.parameters
            parsed.can_execute = True  # System queries don't need device
        
        elif isinstance(intent, CalendarQueryIntent):
            parsed.action = intent.action.value if intent.action else None
            parsed.parameters = {
                "date_range": intent.date_range,
                "search_term": intent.search_term,
            }
            parsed.can_execute = True  # Calendar queries are always executable
        
        elif isinstance(intent, CalendarCreateIntent):
            parsed.action = intent.action.value if intent.action else None
            parsed.parameters = {
                "event_title": intent.event_title,
                "event_date": intent.event_date,
                "event_time": intent.event_time,
                "duration_minutes": intent.duration_minutes,
                "is_all_day": intent.is_all_day,
                "location": intent.location,
                "recurrence": intent.recurrence,
                "edit_field": intent.edit_field,
                "edit_value": intent.edit_value,
            }
            parsed.can_execute = True  # Calendar create actions are always executable
        
        elif isinstance(intent, DocQueryIntent):
            parsed.action = intent.action.value if intent.action else None
            parsed.parameters = {
                "doc_url": intent.doc_url,
                "doc_id": intent.doc_id,
                "meeting_search": intent.meeting_search,
                "meeting_time": intent.meeting_time,
                "question": intent.question,
                "device_name": intent.device_name,
            }
            parsed.can_execute = True  # Doc queries are always executable
        
        elif isinstance(intent, ConversationIntent):
            parsed.can_execute = True  # Conversations are always "executable"
        
        return parsed


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
intent_parser = IntentParser()
