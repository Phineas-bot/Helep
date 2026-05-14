"""Shared test fixtures and configuration."""
import asyncio
import os
import pytest
import httpx
import time
from typing import Dict, Any


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def http_client():
    """HTTP client for testing APIs."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


@pytest.fixture(scope="session")
def test_user():
    """Test user data."""
    return {
        "phone": "+237600000001",
        "password": "testpass123",
        "role": "citizen"
    }


@pytest.fixture(scope="session")
def test_sos():
    """Test SOS incident data."""
    return {
        "lat": 37.7749,
        "lon": -122.4194,
        "mode": "online"
    }


@pytest.fixture(scope="session")
def service_urls():
    """Service URLs for testing."""
    return {
        "user": "http://localhost:8001",
        "sos": "http://localhost:8002",
        "dispatch": "http://localhost:8003",
        "notification": "http://localhost:8004",
        "analytics": "http://localhost:8005"
    }


@pytest.fixture(scope="session")
async def wait_for_services(service_urls):
    """Wait for all services to be ready."""
    max_attempts = 30
    attempt = 0

    while attempt < max_attempts:
        all_ready = True
        for name, url in service_urls.items():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{url}/readyz")
                    if response.status_code != 200:
                        all_ready = False
                        break
            except Exception:
                all_ready = False
                break

        if all_ready:
            print("All services are ready!")
            return

        attempt += 1
        print(f"Waiting for services... (attempt {attempt}/{max_attempts})")
        await asyncio.sleep(2)

    pytest.fail("Services did not become ready within timeout")


@pytest.fixture(scope="session")
async def auth_token(http_client, service_urls, test_user, wait_for_services):
    """Get authentication token for test user."""
    # Register user
    register_data = {
        "phone": test_user["phone"],
        "password": test_user["password"],
        "role": test_user["role"]
    }

    response = await http_client.post(
        f"{service_urls['user']}/signup",
        json=register_data
    )
    assert response.status_code == 201
    signup_result = response.json()

    # Login to get token
    login_data = {
        "phone": test_user["phone"],
        "password": test_user["password"]
    }

    response = await http_client.post(
        f"{service_urls['user']}/login",
        json=login_data
    )
    assert response.status_code == 200
    login_result = response.json()

    return login_result["token"]