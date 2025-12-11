"""
Action Response Schemas - Sprint 3.6

Structured schemas for GPT-4o's JSON responses.

GPT-4o must always return one of these response types:
1. ActionResponse - Execute specific actions
2. ClarificationResponse - Ask user for more info
3. ActionSequenceResponse - Execute multiple actions in order

Design:
=======
- Type-safe Pydantic models
- Clear validation rules
- Easy serialization/deserialization
- Graceful error handling

Usage:
======
```python
from app.ai.schemas.action_response import parse_action_response

# GPT returns JSON string
gpt_json = '{"type": "action", "action_name": "show_calendar", ...}'

# Parse and validate
response = parse_action_response(gpt_json)

if isinstance(response, ActionResponse):
    # Execute the action
    execute(response.action_name, response.parameters)
elif isinstance(response, ClarificationResponse):
    # Ask user for clarification
    return response.message
```
"""

import json
import logging
from typing import Optional, Dict, Any, List, Union
from enum import Enum

from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger("jarvis.ai.action_response")


# ---------------------------------------------------------------------------
# RESPONSE TYPE ENUM
# ---------------------------------------------------------------------------

class ResponseType(str, Enum):
    """Type of response from GPT-4o."""
    ACTION = "action"
    CLARIFICATION = "clarification"
    ACTION_SEQUENCE = "action_sequence"


# ---------------------------------------------------------------------------
# ACTION RESPONSE
# ---------------------------------------------------------------------------

class ActionResponse(BaseModel):
    """
    Response indicating GPT wants to execute an action.
    
    Example:
    ```json
    {
      "type": "action",
      "action_name": "show_calendar",
      "parameters": {
        "target_device": "Living Room TV",
        "date": "2025-12-06"
      }
    }
    ```
    """
    type: ResponseType = Field(default=ResponseType.ACTION)
    action_name: str = Field(
        description="Name of the action to execute (show_calendar, power_on, etc.)"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters (device, date, input, level, etc.)"
    )
    
    # Optional metadata
    reasoning: Optional[str] = Field(
        default=None,
        description="Why GPT chose this action"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this action (0-1)"
    )
    
    @field_validator('action_name')
    @classmethod
    def validate_action_name(cls, v: str) -> str:
        """Validate action name is not empty."""
        if not v or not v.strip():
            raise ValueError("action_name cannot be empty")
        return v.strip().lower()
    
    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure parameters is a dict."""
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError("parameters must be a dictionary")
        return v
    
    def get_target_device(self) -> Optional[str]:
        """Extract target device from parameters."""
        return (
            self.parameters.get("target_device") or
            self.parameters.get("device") or
            self.parameters.get("device_name")
        )
    
    def get_date(self) -> Optional[str]:
        """Extract date from parameters (for calendar actions)."""
        return self.parameters.get("date")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "action_name": self.action_name,
            "parameters": self.parameters,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# CLARIFICATION RESPONSE
# ---------------------------------------------------------------------------

class ClarificationResponse(BaseModel):
    """
    Response indicating GPT needs more information from the user.
    
    Example:
    ```json
    {
      "type": "clarification",
      "message": "Which device would you like to display the calendar on?",
      "suggested_options": ["Living Room TV", "Bedroom Monitor"]
    }
    ```
    """
    type: ResponseType = Field(default=ResponseType.CLARIFICATION)
    message: str = Field(
        description="Question to ask the user"
    )
    suggested_options: Optional[List[str]] = Field(
        default=None,
        description="Suggested options for the user to choose from"
    )
    
    # Context about what's missing
    missing_info: Optional[str] = Field(
        default=None,
        description="What information is needed (device, date, etc.)"
    )
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate message is not empty."""
        if not v or not v.strip():
            raise ValueError("message cannot be empty")
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "message": self.message,
            "suggested_options": self.suggested_options,
            "missing_info": self.missing_info,
        }


# ---------------------------------------------------------------------------
# ACTION SEQUENCE RESPONSE
# ---------------------------------------------------------------------------

class ActionSequenceResponse(BaseModel):
    """
    Response indicating GPT wants to execute multiple actions in sequence.
    
    Example:
    ```json
    {
      "type": "action_sequence",
      "actions": [
        {
          "action_name": "power_on",
          "parameters": {"target_device": "TV"}
        },
        {
          "action_name": "show_calendar",
          "parameters": {"target_device": "TV", "date": "2025-12-06"}
        }
      ]
    }
    ```
    """
    type: ResponseType = Field(default=ResponseType.ACTION_SEQUENCE)
    actions: List[ActionResponse] = Field(
        description="List of actions to execute in order"
    )
    
    # Optional metadata
    reasoning: Optional[str] = Field(
        default=None,
        description="Why this sequence is needed"
    )
    
    @field_validator('actions')
    @classmethod
    def validate_actions(cls, v: List[ActionResponse]) -> List[ActionResponse]:
        """Validate actions list is not empty."""
        if not v:
            raise ValueError("actions list cannot be empty")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "actions": [action.to_dict() for action in self.actions],
            "reasoning": self.reasoning,
        }


# ---------------------------------------------------------------------------
# UNION TYPE
# ---------------------------------------------------------------------------

ActionResponseUnion = Union[ActionResponse, ClarificationResponse, ActionSequenceResponse]


# ---------------------------------------------------------------------------
# RESPONSE PARSER
# ---------------------------------------------------------------------------

class ResponseParseError(Exception):
    """Raised when response parsing fails."""
    pass


def parse_action_response(
    json_str: str,
    strict: bool = False,
) -> ActionResponseUnion:
    """
    Parse GPT-4o's JSON response into a typed response object.
    
    This function:
    1. Parses JSON string
    2. Validates structure
    3. Returns appropriate typed object
    4. Handles errors gracefully
    
    Args:
        json_str: JSON string from GPT-4o
        strict: If True, raise errors; if False, return clarification on error
        
    Returns:
        ActionResponse, ClarificationResponse, or ActionSequenceResponse
        
    Raises:
        ResponseParseError: If strict=True and parsing fails
        
    Example:
        ```python
        response = parse_action_response(gpt_output)
        
        if isinstance(response, ActionResponse):
            execute_action(response)
        elif isinstance(response, ClarificationResponse):
            ask_user(response.message)
        ```
    """
    try:
        # Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from GPT: {e}")
            # Sprint 3.6 fix: Log the actual GPT response for debugging
            logger.error(f"GPT raw response (first 500 chars): {json_str[:500]}")
            
            if strict:
                raise ResponseParseError(f"Invalid JSON: {e}")
            
            # Sprint 3.6 fix: If GPT returned readable plain text, show it to the user
            # instead of a generic "rephrase" message. GPT often returns helpful
            # explanations when it can't fulfill a request.
            if json_str and len(json_str.strip()) > 10:
                # Clean up the response - remove any partial JSON
                clean_response = json_str.strip()
                # Truncate if too long
                if len(clean_response) > 400:
                    clean_response = clean_response[:397] + "..."
                return ClarificationResponse(
                    message=clean_response,
                    missing_info="gpt_plain_text_response",
                )
            
            # Fallback for empty or very short responses
            return ClarificationResponse(
                message="I couldn't process that request. Please try rephrasing.",
                missing_info="parse_error",
            )
        
        # Check for type field
        if not isinstance(data, dict):
            logger.error(f"Response is not a dictionary: {type(data)}")
            if strict:
                raise ResponseParseError("Response must be a JSON object")
            return ClarificationResponse(
                message="I'm not sure how to process that. Can you be more specific?",
                missing_info="valid_request",
            )
        
        response_type = data.get("type", "").lower()
        
        # Route to appropriate parser
        if response_type == "action":
            return _parse_action(data, strict)
        
        elif response_type == "clarification":
            return _parse_clarification(data, strict)
        
        elif response_type == "action_sequence":
            return _parse_action_sequence(data, strict)
        
        else:
            logger.warning(f"Unknown response type: {response_type}")
            if strict:
                raise ResponseParseError(f"Unknown response type: {response_type}")
            return ClarificationResponse(
                message="I'm not sure what you're asking for. Could you clarify?",
                missing_info="clear_intent",
            )
    
    except Exception as e:
        logger.error(f"Unexpected error parsing response: {e}", exc_info=True)
        if strict:
            raise ResponseParseError(f"Parse error: {e}")
        return ClarificationResponse(
            message="I encountered an error processing that. Could you try again?",
            missing_info="error_recovery",
        )


def _parse_action(data: Dict[str, Any], strict: bool) -> Union[ActionResponse, ClarificationResponse]:
    """Parse action response."""
    try:
        return ActionResponse(**data)
    except Exception as e:
        logger.error(f"Failed to parse ActionResponse: {e}")
        if strict:
            raise ResponseParseError(f"Invalid ActionResponse: {e}")
        return ClarificationResponse(
            message="I'm not sure which action to perform. Can you be more specific?",
            missing_info="action_details",
        )


def _parse_clarification(data: Dict[str, Any], strict: bool) -> Union[ClarificationResponse, ClarificationResponse]:
    """Parse clarification response."""
    try:
        return ClarificationResponse(**data)
    except Exception as e:
        logger.error(f"Failed to parse ClarificationResponse: {e}")
        if strict:
            raise ResponseParseError(f"Invalid ClarificationResponse: {e}")
        return ClarificationResponse(
            message="Could you please rephrase your request?",
            missing_info="clear_request",
        )


def _parse_action_sequence(data: Dict[str, Any], strict: bool) -> Union[ActionSequenceResponse, ClarificationResponse]:
    """Parse action sequence response."""
    try:
        # Parse each action in the sequence
        actions_data = data.get("actions", [])
        actions = []
        
        for action_data in actions_data:
            # Ensure type is set for individual actions
            if "type" not in action_data:
                action_data["type"] = "action"
            
            action = ActionResponse(**action_data)
            actions.append(action)
        
        return ActionSequenceResponse(
            actions=actions,
            reasoning=data.get("reasoning"),
        )
    
    except Exception as e:
        logger.error(f"Failed to parse ActionSequenceResponse: {e}")
        if strict:
            raise ResponseParseError(f"Invalid ActionSequenceResponse: {e}")
        return ClarificationResponse(
            message="I'm having trouble understanding that sequence. Could you break it down?",
            missing_info="action_sequence",
        )


# ---------------------------------------------------------------------------
# VALIDATION HELPERS
# ---------------------------------------------------------------------------

def validate_action_parameters(
    action_name: str,
    parameters: Dict[str, Any],
) -> tuple[bool, Optional[str]]:
    """
    Validate that parameters are appropriate for the given action.
    
    Returns:
        (is_valid, error_message)
    """
    # Required parameters for each action type
    action_requirements = {
        "show_calendar": ["target_device"],  # date is optional (defaults to today)
        "show_content": ["target_device", "url"],
        "clear_content": ["target_device"],
        "power_on": ["target_device"],
        "power_off": ["target_device"],
        "set_input": ["target_device", "input"],
        "volume_set": ["target_device", "level"],
        "volume_up": ["target_device"],
        "volume_down": ["target_device"],
        "mute": ["target_device"],
        "unmute": ["target_device"],
    }
    
    required = action_requirements.get(action_name, [])
    
    # Check for required parameters
    for param in required:
        # Check multiple possible parameter names
        if param == "target_device":
            if not (parameters.get("target_device") or 
                    parameters.get("device") or 
                    parameters.get("device_name")):
                return False, f"Missing required parameter: target_device"
        elif param not in parameters:
            return False, f"Missing required parameter: {param}"
    
    return True, None


def is_calendar_action(action_name: str) -> bool:
    """Check if action is calendar-related."""
    return action_name in ["show_calendar", "calendar"]


def is_content_action(action_name: str) -> bool:
    """Check if action is content-related."""
    return action_name in ["show_content", "show_calendar", "clear_content"]


def is_device_control_action(action_name: str) -> bool:
    """Check if action is a basic device control."""
    return action_name in [
        "power_on", "power_off", 
        "set_input",
        "volume_up", "volume_down", "volume_set",
        "mute", "unmute",
    ]
