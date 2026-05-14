"""Smoke tests for basic service health and functionality."""
import pytest
import httpx


class TestServiceHealth:
    """Test basic health checks for all services."""

    @pytest.mark.asyncio
    async def test_user_service_health(self, http_client, service_urls):
        """Test user service health endpoints."""
        # Liveness
        response = await http_client.get(f"{service_urls['user']}/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        # Readiness
        response = await http_client.get(f"{service_urls['user']}/readyz")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    @pytest.mark.asyncio
    async def test_sos_service_health(self, http_client, service_urls):
        """Test SOS service health endpoints."""
        response = await http_client.get(f"{service_urls['sos']}/healthz")
        assert response.status_code == 200

        response = await http_client.get(f"{service_urls['sos']}/readyz")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_service_health(self, http_client, service_urls):
        """Test dispatch service health endpoints."""
        response = await http_client.get(f"{service_urls['dispatch']}/healthz")
        assert response.status_code == 200

        response = await http_client.get(f"{service_urls['dispatch']}/readyz")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_notification_service_health(self, http_client, service_urls):
        """Test notification service health endpoints."""
        response = await http_client.get(f"{service_urls['notification']}/healthz")
        assert response.status_code == 200

        response = await http_client.get(f"{service_urls['notification']}/readyz")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_analytics_service_health(self, http_client, service_urls):
        """Test analytics service health endpoints."""
        response = await http_client.get(f"{service_urls['analytics']}/healthz")
        assert response.status_code == 200

        response = await http_client.get(f"{service_urls['analytics']}/readyz")
        assert response.status_code == 200


class TestBasicFunctionality:
    """Test basic API functionality."""

    @pytest.mark.asyncio
    async def test_user_registration(self, http_client, service_urls, test_user):
        """Test user registration."""
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

        result = response.json()
        assert "id" in result
        assert "token" in result
        assert len(result["token"]) > 0

    @pytest.mark.asyncio
    async def test_user_login(self, http_client, service_urls, test_user):
        """Test user login after registration."""
        # First register
        register_data = {
            "phone": test_user["phone"],
            "password": test_user["password"],
            "role": test_user["role"]
        }

        await http_client.post(
            f"{service_urls['user']}/signup",
            json=register_data
        )

        # Then login
        login_data = {
            "phone": test_user["phone"],
            "password": test_user["password"]
        }

        response = await http_client.post(
            f"{service_urls['user']}/login",
            json=login_data
        )
        assert response.status_code == 200

        result = response.json()
        assert "id" in result
        assert "token" in result

    @pytest.mark.asyncio
    async def test_user_profile(self, http_client, service_urls, auth_token):
        """Test getting user profile with authentication."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = await http_client.get(
            f"{service_urls['user']}/me",
            headers=headers
        )
        assert response.status_code == 200

        profile = response.json()
        assert "id" in profile
        assert "phone" in profile
        assert "role" in profile
        assert "credibility" in profile

    @pytest.mark.asyncio
    async def test_sos_trigger_requires_auth(self, http_client, service_urls, test_sos):
        """Test that SOS trigger requires authentication."""
        response = await http_client.post(
            f"{service_urls['sos']}/sos",
            json=test_sos
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_analytics_empty_stats(self, http_client, service_urls):
        """Test analytics returns valid structure even with no data."""
        response = await http_client.get(f"{service_urls['analytics']}/stats/events")
        assert response.status_code == 200

        stats = response.json()
        assert isinstance(stats, dict)
        # Should have some structure even if empty


class TestMetrics:
    """Test Prometheus metrics exposure."""

    @pytest.mark.asyncio
    async def test_user_service_metrics(self, http_client, service_urls):
        """Test user service exposes Prometheus metrics."""
        response = await http_client.get(f"{service_urls['user']}/metrics")
        assert response.status_code == 200

        metrics = response.text
        assert "helep_user_signups_total" in metrics
        assert "helep_user_logins_total" in metrics

    @pytest.mark.asyncio
    async def test_sos_service_metrics(self, http_client, service_urls):
        """Test SOS service exposes Prometheus metrics."""
        response = await http_client.get(f"{service_urls['sos']}/metrics")
        assert response.status_code == 200

        metrics = response.text
        assert "helep_sos_triggers_total" in metrics
        assert "helep_sos_cancels_total" in metrics