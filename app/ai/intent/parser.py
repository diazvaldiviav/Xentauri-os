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
    ConversationIntent,
    ParsedCommand,
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
            context: Optional context (available devices, user info)
            
        Returns:
            Typed Intent object (DeviceCommand, DeviceQuery, etc.)
        """
        start_time = time.time()
        logger.info(f"Parsing intent: {text[:50]}...")
        
        # Build context string
        context_str = ""
        if context:
            if "devices" in context:
                device_names = [d.get("name", "Unknown") for d in context["devices"]]
                context_str = f"\n\nAvailable devices: {', '.join(device_names)}"
        
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
        parameters = data.get("parameters")
        
        # Map action string to ActionType
        action = self._map_action(action_str)
        
        return DeviceCommand(
            confidence=confidence,
            original_text=original_text,
            reasoning=reasoning,
            device_name=device_name,
            action=action,
            parameters=parameters,
        )
    
    def _create_device_query(
        self,
        data: Dict[str, Any],
        original_text: str,
        confidence: float,
        reasoning: Optional[str],
    ) -> DeviceQuery:
        """Create a DeviceQuery intent."""
        device_name = data.get("device_name", "unknown device")
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
        
        elif isinstance(intent, ConversationIntent):
            parsed.can_execute = True  # Conversations are always "executable"
        
        return parsed


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
intent_parser = IntentParser()
