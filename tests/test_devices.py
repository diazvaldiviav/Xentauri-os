"""
Tests for device CRUD endpoints.

These tests verify:
- Device creation with pairing code generation
- Device listing (all and filtered)
- Device retrieval by ID
- Device updates
- Device deletion
- Pairing code generation
- Device pairing with agent
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.device import Device


class TestDeviceCreate:
    """Tests for POST /devices endpoint."""
    
    def test_create_device_success(self, client: TestClient, auth_headers: dict):
        """Should create a device and return a pairing code."""
        response = client.post(
            "/devices",
            json={"name": "Living Room TV"},
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check device data
        assert data["device"]["name"] == "Living Room TV"
        assert data["device"]["agent_id"] is None
        assert data["device"]["is_online"] is False
        
        # Check pairing code
        assert "pairing_code" in data
        assert len(data["pairing_code"]) == 6
        assert "pairing_expires_at" in data
    
    def test_create_device_without_auth(self, client: TestClient):
        """Should reject unauthenticated requests."""
        response = client.post(
            "/devices",
            json={"name": "Living Room TV"},
        )
        
        assert response.status_code == 403  # No auth header
    
    def test_create_device_empty_name(self, client: TestClient, auth_headers: dict):
        """Should reject empty device names."""
        response = client.post(
            "/devices",
            json={"name": ""},
            headers=auth_headers,
        )
        
        assert response.status_code == 422  # Validation error


class TestDeviceList:
    """Tests for GET /devices endpoint."""
    
    def test_list_devices_empty(self, client: TestClient, auth_headers: dict):
        """Should return empty list when user has no devices."""
        response = client.get("/devices", headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_list_devices_with_devices(
        self, client: TestClient, auth_headers: dict, test_device: Device
    ):
        """Should return user's devices."""
        response = client.get("/devices", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["name"] == "Test TV"
    
    def test_list_devices_online_only_filter(
        self, client: TestClient, auth_headers: dict, test_device: Device
    ):
        """Should filter to online devices only."""
        response = client.get("/devices?online_only=true", headers=auth_headers)
        
        assert response.status_code == 200
        # Device is offline, so empty list
        assert response.json() == []


class TestDeviceGet:
    """Tests for GET /devices/{device_id} endpoint."""
    
    def test_get_device_success(
        self, client: TestClient, auth_headers: dict, test_device: Device
    ):
        """Should return device details."""
        response = client.get(f"/devices/{test_device.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(test_device.id)
        assert data["name"] == "Test TV"
    
    def test_get_device_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent device."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/devices/{fake_id}", headers=auth_headers)
        
        assert response.status_code == 404


class TestDeviceUpdate:
    """Tests for PATCH /devices/{device_id} endpoint."""
    
    def test_update_device_name(
        self, client: TestClient, auth_headers: dict, test_device: Device
    ):
        """Should update device name."""
        response = client.patch(
            f"/devices/{test_device.id}",
            json={"name": "Bedroom TV"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        assert response.json()["name"] == "Bedroom TV"
    
    def test_update_device_capabilities(
        self, client: TestClient, auth_headers: dict, test_device: Device
    ):
        """Should update device capabilities."""
        capabilities = {"power": True, "volume": True, "input": ["hdmi1", "hdmi2"]}
        
        response = client.patch(
            f"/devices/{test_device.id}",
            json={"capabilities": capabilities},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        assert response.json()["capabilities"] == capabilities


class TestDeviceDelete:
    """Tests for DELETE /devices/{device_id} endpoint."""
    
    def test_delete_device_success(
        self, client: TestClient, auth_headers: dict, test_device: Device, db: Session
    ):
        """Should delete device."""
        response = client.delete(f"/devices/{test_device.id}", headers=auth_headers)
        
        assert response.status_code == 204
        
        # Verify device is deleted
        deleted = db.query(Device).filter(Device.id == test_device.id).first()
        assert deleted is None
    
    def test_delete_device_not_found(self, client: TestClient, auth_headers: dict):
        """Should return 404 for non-existent device."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.delete(f"/devices/{fake_id}", headers=auth_headers)
        
        assert response.status_code == 404


class TestPairingCode:
    """Tests for pairing code generation and device pairing."""
    
    def test_generate_new_pairing_code(
        self, client: TestClient, auth_headers: dict, test_device: Device
    ):
        """Should generate a new pairing code for existing device."""
        response = client.post(
            f"/devices/{test_device.id}/pairing-code",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "pairing_code" in data
        assert len(data["pairing_code"]) == 6
        assert "expires_at" in data
    
    def test_pair_device_success(
        self, client: TestClient, auth_headers: dict, db: Session
    ):
        """Should pair device with agent using valid code."""
        # First create a device to get a pairing code
        create_response = client.post(
            "/devices",
            json={"name": "New TV"},
            headers=auth_headers,
        )
        pairing_code = create_response.json()["pairing_code"]
        device_id = create_response.json()["device"]["id"]
        
        # Now pair the device
        pair_response = client.post(
            "/devices/pair",
            params={"agent_id": "pi-agent-xyz"},
            json={"pairing_code": pairing_code},
        )
        
        assert pair_response.status_code == 200
        data = pair_response.json()
        
        assert data["id"] == device_id
        assert data["agent_id"] == "pi-agent-xyz"
    
    def test_pair_device_invalid_code(self, client: TestClient):
        """Should reject invalid pairing code."""
        response = client.post(
            "/devices/pair",
            params={"agent_id": "pi-agent-xyz"},
            json={"pairing_code": "XXXXXX"},  # Valid format but non-existent code
        )
        
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]
    
    def test_pair_device_code_consumed(
        self, client: TestClient, auth_headers: dict
    ):
        """Should reject already-used pairing code."""
        # Create device and get code
        create_response = client.post(
            "/devices",
            json={"name": "New TV"},
            headers=auth_headers,
        )
        pairing_code = create_response.json()["pairing_code"]
        
        # Use the code once
        client.post(
            "/devices/pair",
            params={"agent_id": "pi-agent-1"},
            json={"pairing_code": pairing_code},
        )
        
        # Try to use it again
        response = client.post(
            "/devices/pair",
            params={"agent_id": "pi-agent-2"},
            json={"pairing_code": pairing_code},
        )
        
        assert response.status_code == 400
