"""
Tests for the /intent/agent endpoint (Pi Alexa authentication).

This module tests the agent_id authentication flow for Pi devices
that send voice commands without JWT tokens.

Sprint: 5.0 - Raspberry Pi Agent
"""

import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.device import Device
from app.core.security import hash_password


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def pi_alexa_device(db: Session, test_user: User) -> Device:
    """
    Create a Pi Alexa device (paired with agent_id).

    Returns:
        Device with agent_id="pi-alexa-test-123"
    """
    device = Device(
        id=uuid4(),
        user_id=test_user.id,
        name="Pi Alexa",
        agent_id="pi-alexa-test-123",
        capabilities={"voice_input": True},
        is_online=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@pytest.fixture
def agent_headers(pi_alexa_device: Device) -> dict:
    """
    Create headers with the Pi Alexa agent_id.

    Returns:
        Dict with X-Agent-ID header
    """
    return {"X-Agent-ID": pi_alexa_device.agent_id}


@pytest.fixture
def inactive_user_with_device(db: Session) -> tuple[User, Device]:
    """
    Create an inactive user with a paired device.

    Returns:
        Tuple of (User, Device)
    """
    user = User(
        id=uuid4(),
        email="inactive@example.com",
        hashed_password=hash_password("testpassword"),
        display_name="Inactive User",
        is_active=False,  # Inactive!
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    device = Device(
        id=uuid4(),
        user_id=user.id,
        name="Inactive User Device",
        agent_id="inactive-agent-123",
        capabilities=None,
        is_online=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    return user, device


# ---------------------------------------------------------------------------
# AUTHENTICATION TESTS
# ---------------------------------------------------------------------------

class TestIntentAgentAuthentication:
    """Tests for /intent/agent authentication via X-Agent-ID header."""

    def test_missing_agent_id_header(self, client: TestClient):
        """Test that request without X-Agent-ID header fails with 422."""
        response = client.post(
            "/intent/agent",
            json={"text": "hello"},
        )

        assert response.status_code == 422  # Validation error (missing required header)

    def test_invalid_agent_id(self, client: TestClient):
        """Test that invalid/unpaired agent_id fails with 401."""
        response = client.post(
            "/intent/agent",
            headers={"X-Agent-ID": "invalid-agent-not-paired"},
            json={"text": "hello"},
        )

        assert response.status_code == 401
        assert "not paired" in response.json()["detail"].lower()

    def test_inactive_user_agent(
        self,
        client: TestClient,
        inactive_user_with_device: tuple[User, Device]
    ):
        """Test that agent of inactive user fails with 403."""
        user, device = inactive_user_with_device

        response = client.post(
            "/intent/agent",
            headers={"X-Agent-ID": device.agent_id},
            json={"text": "hello"},
        )

        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()

    def test_valid_agent_id_authenticates(
        self,
        client: TestClient,
        pi_alexa_device: Device
    ):
        """Test that valid agent_id authenticates successfully."""
        # Mock the intent_service to avoid actual AI calls
        with patch(
            "app.routers.intent.intent_service.process",
            new_callable=AsyncMock
        ) as mock_process:
            # Setup mock return value
            from app.services.intent_service import IntentResult, IntentResultType
            mock_process.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CONVERSATION,
                confidence=0.95,
                message="Hello! How can I help you?",
            )

            response = client.post(
                "/intent/agent",
                headers={"X-Agent-ID": pi_alexa_device.agent_id},
                json={"text": "hello"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Hello! How can I help you?"


# ---------------------------------------------------------------------------
# ENDPOINT FUNCTIONALITY TESTS
# ---------------------------------------------------------------------------

class TestIntentAgentEndpoint:
    """Tests for /intent/agent endpoint functionality."""

    def test_response_format_matches_intent(
        self,
        client: TestClient,
        pi_alexa_device: Device
    ):
        """Test that /intent/agent returns same format as /intent."""
        with patch(
            "app.routers.intent.intent_service.process",
            new_callable=AsyncMock
        ) as mock_process:
            from app.services.intent_service import IntentResult, IntentResultType
            mock_process.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=0.92,
                action="power_on",
                parameters={"device": "TV"},
                command_sent=True,
                command_id="cmd-123",
                message="Turning on the TV",
            )

            response = client.post(
                "/intent/agent",
                headers={"X-Agent-ID": pi_alexa_device.agent_id},
                json={"text": "turn on the TV"},
            )

            assert response.status_code == 200
            data = response.json()

            # Verify all expected fields are present
            assert "success" in data
            assert "intent_type" in data
            assert "confidence" in data
            assert "action" in data
            assert "parameters" in data
            assert "command_sent" in data
            assert "command_id" in data
            assert "message" in data

    def test_conversation_history_saved(
        self,
        client: TestClient,
        pi_alexa_device: Device,
        test_user: User
    ):
        """Test that conversation history is saved after processing."""
        with patch(
            "app.routers.intent.intent_service.process",
            new_callable=AsyncMock
        ) as mock_process:
            from app.services.intent_service import IntentResult, IntentResultType
            mock_process.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CONVERSATION,
                confidence=0.9,
                message="I can help with that!",
            )

            # Mock the service module that gets imported inside the function
            with patch(
                "app.services.conversation_context_service.conversation_context_service.add_conversation_turn"
            ) as mock_add_turn:
                response = client.post(
                    "/intent/agent",
                    headers={"X-Agent-ID": pi_alexa_device.agent_id},
                    json={"text": "can you help me?"},
                )

                assert response.status_code == 200

                # Verify conversation was saved
                mock_add_turn.assert_called_once()
                call_args = mock_add_turn.call_args
                assert call_args.kwargs["user_message"] == "can you help me?"
                assert call_args.kwargs["assistant_response"] == "I can help with that!"

    def test_device_id_passed_to_service(
        self,
        client: TestClient,
        pi_alexa_device: Device
    ):
        """Test that optional device_id is passed to intent_service."""
        target_device_id = str(uuid4())

        with patch(
            "app.routers.intent.intent_service.process",
            new_callable=AsyncMock
        ) as mock_process:
            from app.services.intent_service import IntentResult, IntentResultType
            mock_process.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=0.9,
                message="Command sent",
            )

            response = client.post(
                "/intent/agent",
                headers={"X-Agent-ID": pi_alexa_device.agent_id},
                json={"text": "turn on", "device_id": target_device_id},
            )

            assert response.status_code == 200

            # Verify device_id was passed
            mock_process.assert_called_once()
            call_kwargs = mock_process.call_args.kwargs
            assert str(call_kwargs["device_id"]) == target_device_id

    def test_empty_text_rejected(
        self,
        client: TestClient,
        pi_alexa_device: Device
    ):
        """Test that empty text is rejected with 422."""
        response = client.post(
            "/intent/agent",
            headers={"X-Agent-ID": pi_alexa_device.agent_id},
            json={"text": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_text_too_long_rejected(
        self,
        client: TestClient,
        pi_alexa_device: Device
    ):
        """Test that text over 500 chars is rejected."""
        long_text = "a" * 501

        response = client.post(
            "/intent/agent",
            headers={"X-Agent-ID": pi_alexa_device.agent_id},
            json={"text": long_text},
        )

        assert response.status_code == 422  # Validation error


# ---------------------------------------------------------------------------
# COMPARISON TESTS (Agent vs JWT)
# ---------------------------------------------------------------------------

class TestAgentVsJwtParity:
    """Tests to verify /intent/agent behaves same as /intent."""

    def test_same_user_same_result(
        self,
        client: TestClient,
        test_user: User,
        pi_alexa_device: Device,
        auth_headers: dict
    ):
        """Test that same user gets same result via agent or JWT."""
        test_text = "what time is it"

        mock_result = None

        def create_mock_result(*args, **kwargs):
            from app.services.intent_service import IntentResult, IntentResultType
            return IntentResult(
                success=True,
                intent_type=IntentResultType.CONVERSATION,
                confidence=0.95,
                message="It's 3:00 PM",
            )

        with patch(
            "app.routers.intent.intent_service.process",
            new_callable=AsyncMock,
            side_effect=create_mock_result
        ):
            # Call via JWT
            jwt_response = client.post(
                "/intent",
                headers=auth_headers,
                json={"text": test_text},
            )

            # Call via agent_id
            agent_response = client.post(
                "/intent/agent",
                headers={"X-Agent-ID": pi_alexa_device.agent_id},
                json={"text": test_text},
            )

            # Both should succeed
            assert jwt_response.status_code == 200
            assert agent_response.status_code == 200

            # Same response structure
            jwt_data = jwt_response.json()
            agent_data = agent_response.json()

            assert jwt_data["success"] == agent_data["success"]
            assert jwt_data["intent_type"] == agent_data["intent_type"]
            assert jwt_data["message"] == agent_data["message"]


# ---------------------------------------------------------------------------
# ERROR HANDLING TESTS
# ---------------------------------------------------------------------------

class TestIntentAgentErrorHandling:
    """Tests for error handling in /intent/agent."""

    def test_service_exception_returns_500(
        self,
        client: TestClient,
        pi_alexa_device: Device
    ):
        """Test that service exceptions return 500."""
        with patch(
            "app.routers.intent.intent_service.process",
            new_callable=AsyncMock,
            side_effect=Exception("AI service unavailable")
        ):
            response = client.post(
                "/intent/agent",
                headers={"X-Agent-ID": pi_alexa_device.agent_id},
                json={"text": "hello"},
            )

            assert response.status_code == 500
            assert "Failed to process intent" in response.json()["detail"]
