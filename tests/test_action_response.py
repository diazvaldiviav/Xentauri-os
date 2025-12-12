"""
Tests for AI Action Response Schemas - Phase 1

Tests for:
- ActionResponse validation and methods
- ClarificationResponse validation
- ActionSequenceResponse validation
- parse_action_response() parser function
- Validation helper functions

These tests ensure GPT-4o's JSON responses are correctly
parsed and validated before execution.
"""

import pytest
import json
from typing import Dict, Any

from app.ai.schemas.action_response import (
    # Schemas
    ResponseType,
    ActionResponse,
    ClarificationResponse,
    ActionSequenceResponse,
    ActionResponseUnion,
    # Parser
    parse_action_response,
    ResponseParseError,
    # Validators
    validate_action_parameters,
    is_calendar_action,
    is_content_action,
    is_device_control_action,
)


# ===========================================================================
# ACTIONRESPONSE TESTS
# ===========================================================================

class TestActionResponse:
    """Tests for ActionResponse schema."""
    
    def test_create_basic_action(self):
        """Test creating a basic action response."""
        action = ActionResponse(
            action_name="power_on",
            parameters={"target_device": "Living Room TV"},
        )
        
        assert action.type == ResponseType.ACTION
        assert action.action_name == "power_on"
        assert action.parameters["target_device"] == "Living Room TV"
        assert action.confidence == 1.0
        assert action.reasoning is None
    
    def test_create_action_with_all_fields(self):
        """Test creating action with all optional fields."""
        action = ActionResponse(
            action_name="show_calendar",
            parameters={
                "target_device": "Kitchen Display",
                "date": "2025-12-25",
            },
            reasoning="User wants to see Christmas schedule",
            confidence=0.95,
        )
        
        assert action.action_name == "show_calendar"
        assert action.get_date() == "2025-12-25"
        assert action.get_target_device() == "Kitchen Display"
        assert action.confidence == 0.95
        assert "Christmas" in action.reasoning
    
    def test_action_name_normalized_to_lowercase(self):
        """Test that action names are normalized to lowercase."""
        action = ActionResponse(
            action_name="  POWER_ON  ",
            parameters={},
        )
        assert action.action_name == "power_on"
    
    def test_empty_action_name_raises_error(self):
        """Test that empty action name is rejected."""
        with pytest.raises(ValueError, match="action_name cannot be empty"):
            ActionResponse(action_name="", parameters={})
    
    def test_whitespace_action_name_raises_error(self):
        """Test that whitespace-only action name is rejected."""
        with pytest.raises(ValueError, match="action_name cannot be empty"):
            ActionResponse(action_name="   ", parameters={})
    
    def test_none_parameters_rejected_by_pydantic(self):
        """Test that None parameters is rejected (Pydantic requires dict)."""
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            ActionResponse(
                action_name="power_off",
                parameters=None,
            )
    
    def test_invalid_parameters_type_raises_error(self):
        """Test that non-dict parameters raises Pydantic ValidationError."""
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            ActionResponse(
                action_name="power_on",
                parameters="not a dict",  # type: ignore
            )
    
    def test_confidence_bounds_validation(self):
        """Test that confidence must be between 0 and 1."""
        # Valid low bound
        action = ActionResponse(action_name="test", parameters={}, confidence=0.0)
        assert action.confidence == 0.0
        
        # Valid high bound
        action = ActionResponse(action_name="test", parameters={}, confidence=1.0)
        assert action.confidence == 1.0
        
        # Invalid: too high
        with pytest.raises(ValueError):
            ActionResponse(action_name="test", parameters={}, confidence=1.5)
        
        # Invalid: too low
        with pytest.raises(ValueError):
            ActionResponse(action_name="test", parameters={}, confidence=-0.1)
    
    def test_get_target_device_variants(self):
        """Test that get_target_device() handles different parameter names."""
        # Using target_device
        action1 = ActionResponse(
            action_name="power_on",
            parameters={"target_device": "TV1"},
        )
        assert action1.get_target_device() == "TV1"
        
        # Using device
        action2 = ActionResponse(
            action_name="power_on",
            parameters={"device": "TV2"},
        )
        assert action2.get_target_device() == "TV2"
        
        # Using device_name
        action3 = ActionResponse(
            action_name="power_on",
            parameters={"device_name": "TV3"},
        )
        assert action3.get_target_device() == "TV3"
        
        # None when missing
        action4 = ActionResponse(
            action_name="power_on",
            parameters={"something_else": "value"},
        )
        assert action4.get_target_device() is None
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        action = ActionResponse(
            action_name="show_calendar",
            parameters={"target_device": "TV", "date": "2025-12-12"},
            reasoning="Show today's events",
            confidence=0.9,
        )
        
        d = action.to_dict()
        
        assert d["type"] == "action"
        assert d["action_name"] == "show_calendar"
        assert d["parameters"]["target_device"] == "TV"
        assert d["parameters"]["date"] == "2025-12-12"
        assert d["reasoning"] == "Show today's events"
        assert d["confidence"] == 0.9


# ===========================================================================
# CLARIFICATIONRESPONSE TESTS
# ===========================================================================

class TestClarificationResponse:
    """Tests for ClarificationResponse schema."""
    
    def test_create_basic_clarification(self):
        """Test creating a basic clarification response."""
        clarification = ClarificationResponse(
            message="Which device would you like to use?",
        )
        
        assert clarification.type == ResponseType.CLARIFICATION
        assert clarification.message == "Which device would you like to use?"
        assert clarification.suggested_options is None
        assert clarification.missing_info is None
    
    def test_create_clarification_with_options(self):
        """Test creating clarification with suggested options."""
        clarification = ClarificationResponse(
            message="Which device?",
            suggested_options=["Living Room TV", "Bedroom Monitor"],
            missing_info="device",
        )
        
        assert len(clarification.suggested_options) == 2
        assert "Living Room TV" in clarification.suggested_options
        assert clarification.missing_info == "device"
    
    def test_empty_message_raises_error(self):
        """Test that empty message is rejected."""
        with pytest.raises(ValueError, match="message cannot be empty"):
            ClarificationResponse(message="")
    
    def test_whitespace_message_raises_error(self):
        """Test that whitespace-only message is rejected."""
        with pytest.raises(ValueError, match="message cannot be empty"):
            ClarificationResponse(message="   ")
    
    def test_message_is_stripped(self):
        """Test that message whitespace is stripped."""
        clarification = ClarificationResponse(
            message="  Which device?  ",
        )
        assert clarification.message == "Which device?"
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        clarification = ClarificationResponse(
            message="Which device?",
            suggested_options=["TV1", "TV2"],
            missing_info="device",
        )
        
        d = clarification.to_dict()
        
        assert d["type"] == "clarification"
        assert d["message"] == "Which device?"
        assert d["suggested_options"] == ["TV1", "TV2"]
        assert d["missing_info"] == "device"


# ===========================================================================
# ACTIONSEQUENCERESPONSE TESTS
# ===========================================================================

class TestActionSequenceResponse:
    """Tests for ActionSequenceResponse schema."""
    
    def test_create_basic_sequence(self):
        """Test creating a sequence with multiple actions."""
        sequence = ActionSequenceResponse(
            actions=[
                ActionResponse(
                    action_name="power_on",
                    parameters={"target_device": "TV"},
                ),
                ActionResponse(
                    action_name="show_calendar",
                    parameters={"target_device": "TV"},
                ),
            ],
        )
        
        assert sequence.type == ResponseType.ACTION_SEQUENCE
        assert len(sequence.actions) == 2
        assert sequence.actions[0].action_name == "power_on"
        assert sequence.actions[1].action_name == "show_calendar"
    
    def test_create_sequence_with_reasoning(self):
        """Test creating sequence with reasoning."""
        sequence = ActionSequenceResponse(
            actions=[
                ActionResponse(action_name="power_on", parameters={"target_device": "TV"}),
            ],
            reasoning="First turn on, then display content",
        )
        
        assert sequence.reasoning == "First turn on, then display content"
    
    def test_empty_actions_raises_error(self):
        """Test that empty actions list is rejected."""
        with pytest.raises(ValueError, match="actions list cannot be empty"):
            ActionSequenceResponse(actions=[])
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        sequence = ActionSequenceResponse(
            actions=[
                ActionResponse(
                    action_name="power_on",
                    parameters={"target_device": "TV"},
                ),
            ],
            reasoning="Turn on first",
        )
        
        d = sequence.to_dict()
        
        assert d["type"] == "action_sequence"
        assert len(d["actions"]) == 1
        assert d["actions"][0]["action_name"] == "power_on"
        assert d["reasoning"] == "Turn on first"


# ===========================================================================
# PARSE_ACTION_RESPONSE TESTS
# ===========================================================================

class TestParseActionResponse:
    """Tests for the parse_action_response() function."""
    
    def test_parse_valid_action(self):
        """Test parsing valid action JSON."""
        json_str = json.dumps({
            "type": "action",
            "action_name": "power_on",
            "parameters": {"target_device": "Living Room TV"},
        })
        
        result = parse_action_response(json_str)
        
        assert isinstance(result, ActionResponse)
        assert result.action_name == "power_on"
        assert result.parameters["target_device"] == "Living Room TV"
    
    def test_parse_valid_clarification(self):
        """Test parsing valid clarification JSON."""
        json_str = json.dumps({
            "type": "clarification",
            "message": "Which device?",
            "suggested_options": ["TV1", "TV2"],
        })
        
        result = parse_action_response(json_str)
        
        assert isinstance(result, ClarificationResponse)
        assert result.message == "Which device?"
        assert len(result.suggested_options) == 2
    
    def test_parse_valid_action_sequence(self):
        """Test parsing valid action sequence JSON."""
        json_str = json.dumps({
            "type": "action_sequence",
            "actions": [
                {"action_name": "power_on", "parameters": {"target_device": "TV"}},
                {"action_name": "show_calendar", "parameters": {"target_device": "TV"}},
            ],
        })
        
        result = parse_action_response(json_str)
        
        assert isinstance(result, ActionSequenceResponse)
        assert len(result.actions) == 2
    
    def test_parse_invalid_json_returns_clarification(self):
        """Test that invalid JSON returns clarification (non-strict mode)."""
        result = parse_action_response("not valid json")
        
        assert isinstance(result, ClarificationResponse)
        # Should return the raw text as the message
        assert "not valid json" in result.message.lower()
    
    def test_parse_invalid_json_strict_raises(self):
        """Test that invalid JSON raises error in strict mode."""
        with pytest.raises(ResponseParseError, match="Invalid JSON"):
            parse_action_response("not valid json", strict=True)
    
    def test_parse_unknown_type_returns_clarification(self):
        """Test that unknown type returns clarification (non-strict)."""
        json_str = json.dumps({
            "type": "unknown_type",
            "data": "something",
        })
        
        result = parse_action_response(json_str)
        
        assert isinstance(result, ClarificationResponse)
    
    def test_parse_unknown_type_strict_raises(self):
        """Test that unknown type raises error in strict mode."""
        json_str = json.dumps({"type": "unknown"})
        
        with pytest.raises(ResponseParseError, match="Unknown response type"):
            parse_action_response(json_str, strict=True)
    
    def test_parse_non_dict_returns_clarification(self):
        """Test that non-dict JSON returns clarification."""
        json_str = json.dumps(["array", "not", "dict"])
        
        result = parse_action_response(json_str)
        
        assert isinstance(result, ClarificationResponse)
    
    def test_parse_action_sequence_adds_type_to_actions(self):
        """Test that action sequence parser adds type to individual actions."""
        json_str = json.dumps({
            "type": "action_sequence",
            "actions": [
                {"action_name": "power_on", "parameters": {}},  # No type field
            ],
        })
        
        result = parse_action_response(json_str)
        
        assert isinstance(result, ActionSequenceResponse)
        assert result.actions[0].type == ResponseType.ACTION
    
    def test_parse_empty_string_returns_clarification(self):
        """Test that empty string returns clarification."""
        result = parse_action_response("")
        
        assert isinstance(result, ClarificationResponse)
    
    def test_parse_requires_lowercase_type(self):
        """Test that type field must be lowercase (enum values are lowercase)."""
        # Uppercase 'ACTION' will fail Pydantic validation
        json_str = json.dumps({
            "type": "ACTION",  # Uppercase - NOT supported
            "action_name": "power_on",
            "parameters": {},
        })
        
        result = parse_action_response(json_str)
        
        # Non-strict mode returns clarification on parse error
        assert isinstance(result, ClarificationResponse)
        
        # Lowercase works correctly
        json_str_lower = json.dumps({
            "type": "action",  # Lowercase - correct
            "action_name": "power_on",
            "parameters": {},
        })
        
        result_lower = parse_action_response(json_str_lower)
        assert isinstance(result_lower, ActionResponse)
    
    def test_parse_gpt_plain_text_response(self):
        """Test that GPT's plain text explanations are shown to user."""
        # When GPT returns readable text instead of JSON
        plain_text = "I apologize, but I cannot perform that action because the device is offline."
        
        result = parse_action_response(plain_text)
        
        assert isinstance(result, ClarificationResponse)
        assert "apologize" in result.message.lower()
        assert result.missing_info == "gpt_plain_text_response"


# ===========================================================================
# VALIDATE_ACTION_PARAMETERS TESTS
# ===========================================================================

class TestValidateActionParameters:
    """Tests for validate_action_parameters() helper."""
    
    def test_valid_show_calendar_parameters(self):
        """Test validation of valid show_calendar parameters."""
        is_valid, error = validate_action_parameters(
            "show_calendar",
            {"target_device": "Living Room TV"},
        )
        
        assert is_valid is True
        assert error is None
    
    def test_missing_target_device(self):
        """Test that missing target_device is caught."""
        is_valid, error = validate_action_parameters(
            "power_on",
            {},  # Missing target_device
        )
        
        assert is_valid is False
        assert "target_device" in error
    
    def test_target_device_aliases_accepted(self):
        """Test that device/device_name are accepted as aliases."""
        # Using 'device' instead of 'target_device'
        is_valid, error = validate_action_parameters(
            "power_on",
            {"device": "TV"},
        )
        assert is_valid is True
        
        # Using 'device_name' instead of 'target_device'
        is_valid, error = validate_action_parameters(
            "power_on",
            {"device_name": "TV"},
        )
        assert is_valid is True
    
    def test_set_input_requires_input_parameter(self):
        """Test that set_input requires both device and input."""
        # Missing input
        is_valid, error = validate_action_parameters(
            "set_input",
            {"target_device": "TV"},
        )
        
        assert is_valid is False
        assert "input" in error
    
    def test_volume_set_requires_level(self):
        """Test that volume_set requires level parameter."""
        is_valid, error = validate_action_parameters(
            "volume_set",
            {"target_device": "TV"},  # Missing level
        )
        
        assert is_valid is False
        assert "level" in error
    
    def test_unknown_action_passes(self):
        """Test that unknown actions pass validation (no requirements)."""
        is_valid, error = validate_action_parameters(
            "unknown_action",
            {},
        )
        
        assert is_valid is True
        assert error is None


# ===========================================================================
# ACTION TYPE CHECKER TESTS
# ===========================================================================

class TestActionTypeCheckers:
    """Tests for action type checker functions."""
    
    def test_is_calendar_action(self):
        """Test is_calendar_action() checker."""
        assert is_calendar_action("show_calendar") is True
        assert is_calendar_action("calendar") is True
        assert is_calendar_action("power_on") is False
        assert is_calendar_action("show_content") is False
    
    def test_is_content_action(self):
        """Test is_content_action() checker."""
        assert is_content_action("show_content") is True
        assert is_content_action("show_calendar") is True
        assert is_content_action("clear_content") is True
        assert is_content_action("power_on") is False
    
    def test_is_device_control_action(self):
        """Test is_device_control_action() checker."""
        assert is_device_control_action("power_on") is True
        assert is_device_control_action("power_off") is True
        assert is_device_control_action("set_input") is True
        assert is_device_control_action("volume_up") is True
        assert is_device_control_action("volume_down") is True
        assert is_device_control_action("volume_set") is True
        assert is_device_control_action("mute") is True
        assert is_device_control_action("unmute") is True
        assert is_device_control_action("show_calendar") is False
        assert is_device_control_action("show_content") is False


# ===========================================================================
# EDGE CASES & INTEGRATION
# ===========================================================================

class TestEdgeCases:
    """Tests for edge cases and integration scenarios."""
    
    def test_parse_and_validate_flow(self):
        """Test full parse → validate flow."""
        json_str = json.dumps({
            "type": "action",
            "action_name": "show_calendar",
            "parameters": {"target_device": "TV", "date": "2025-12-25"},
        })
        
        # Parse
        result = parse_action_response(json_str)
        assert isinstance(result, ActionResponse)
        
        # Validate
        is_valid, error = validate_action_parameters(
            result.action_name,
            result.parameters,
        )
        assert is_valid is True
    
    def test_action_with_special_characters(self):
        """Test action with special characters in parameters."""
        action = ActionResponse(
            action_name="show_content",
            parameters={
                "target_device": "Living Room TV",
                "url": "https://example.com/page?q=test&foo=bar",
            },
        )
        
        assert "https://example.com" in action.parameters["url"]
    
    def test_unicode_in_parameters(self):
        """Test handling of unicode in parameters."""
        action = ActionResponse(
            action_name="power_on",
            parameters={"target_device": "客厅电视"},  # Chinese: Living room TV
        )
        
        assert action.parameters["target_device"] == "客厅电视"
    
    def test_nested_parameters(self):
        """Test handling of nested parameter structures."""
        action = ActionResponse(
            action_name="complex_action",
            parameters={
                "target_device": "TV",
                "settings": {
                    "brightness": 80,
                    "contrast": 50,
                },
            },
        )
        
        assert action.parameters["settings"]["brightness"] == 80
    
    def test_large_suggested_options_list(self):
        """Test clarification with many suggested options."""
        options = [f"Device {i}" for i in range(100)]
        
        clarification = ClarificationResponse(
            message="Which device?",
            suggested_options=options,
        )
        
        assert len(clarification.suggested_options) == 100
    
    def test_very_long_reasoning(self):
        """Test action with very long reasoning text."""
        long_reasoning = "A" * 10000
        
        action = ActionResponse(
            action_name="test",
            parameters={},
            reasoning=long_reasoning,
        )
        
        assert len(action.reasoning) == 10000


# ===========================================================================
# MARKDOWN CODE BLOCK STRIPPING TESTS
# ===========================================================================

class TestMarkdownCodeBlockStripping:
    """Tests for stripping markdown code blocks from GPT responses."""
    
    def test_parse_json_wrapped_in_code_block(self):
        """Test parsing JSON wrapped in ```json ... ```."""
        wrapped_json = '''```json
{
  "type": "action",
  "action_name": "show_calendar",
  "parameters": {
    "target_device": "Living Room TV",
    "date": "2026-03-26"
  }
}
```'''
        
        response = parse_action_response(wrapped_json)
        
        assert isinstance(response, ActionResponse)
        assert response.action_name == "show_calendar"
        assert response.parameters["target_device"] == "Living Room TV"
        assert response.parameters["date"] == "2026-03-26"
    
    def test_parse_json_wrapped_in_plain_code_block(self):
        """Test parsing JSON wrapped in ``` ... ``` (no language hint)."""
        wrapped_json = '''```
{
  "type": "action",
  "action_name": "power_on",
  "parameters": {"target_device": "TV"}
}
```'''
        
        response = parse_action_response(wrapped_json)
        
        assert isinstance(response, ActionResponse)
        assert response.action_name == "power_on"
    
    def test_parse_unwrapped_json(self):
        """Test that unwrapped JSON still works."""
        raw_json = '{"type": "action", "action_name": "power_off", "parameters": {}}'
        
        response = parse_action_response(raw_json)
        
        assert isinstance(response, ActionResponse)
        assert response.action_name == "power_off"
    
    def test_parse_clarification_in_code_block(self):
        """Test parsing clarification wrapped in code block."""
        wrapped_json = '''```json
{
  "type": "clarification",
  "message": "Which device would you like to use?"
}
```'''
        
        response = parse_action_response(wrapped_json)
        
        assert isinstance(response, ClarificationResponse)
        assert "which device" in response.message.lower()
    
    def test_parse_action_sequence_in_code_block(self):
        """Test parsing action sequence wrapped in code block."""
        wrapped_json = '''```json
{
  "type": "action_sequence",
  "actions": [
    {"type": "action", "action_name": "power_on", "parameters": {"target_device": "TV"}},
    {"type": "action", "action_name": "show_calendar", "parameters": {"target_device": "TV"}}
  ]
}
```'''
        
        response = parse_action_response(wrapped_json)
        
        assert isinstance(response, ActionSequenceResponse)
        assert len(response.actions) == 2
    
    def test_code_block_with_extra_whitespace(self):
        """Test code block with extra whitespace around it."""
        wrapped_json = '''   
```json
{"type": "action", "action_name": "test", "parameters": {}}
```
   '''
        
        response = parse_action_response(wrapped_json)
        
        assert isinstance(response, ActionResponse)
        assert response.action_name == "test"
