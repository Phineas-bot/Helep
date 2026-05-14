"""End-to-end saga tests for the complete incident flow."""
import pytest
import asyncio
import httpx
import time


class TestSagaFlow:
    """Test the complete SOS → Dispatch → Notification saga."""

    @pytest.mark.asyncio
    async def test_complete_saga_flow(self, http_client, service_urls, auth_token, test_sos):
        """Test full incident lifecycle from trigger to notification."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Trigger SOS incident
        response = await http_client.post(
            f"{service_urls['sos']}/sos",
            json=test_sos,
            headers=headers
        )
        assert response.status_code == 201

        incident = response.json()
        assert "incident_id" in incident
        assert "status" in incident
        incident_id = incident["incident_id"]

        # Wait for saga to complete (dispatch + notification)
        await asyncio.sleep(3)

        # Check that analytics captured the events
        response = await http_client.get(f"{service_urls['analytics']}/stats/events")
        assert response.status_code == 200

        events = response.json()
        # Should have captured sos.triggered at minimum
        assert events.get("sos.triggered", 0) >= 1

        # Check incident details
        response = await http_client.get(f"{service_urls['sos']}/sos/{incident_id}")
        assert response.status_code == 200

        incident_details = response.json()
        assert incident_details["id"] == incident_id
        assert incident_details["lat"] == test_sos["lat"]
        assert incident_details["lon"] == test_sos["lon"]

    @pytest.mark.asyncio
    async def test_saga_cancellation(self, http_client, service_urls, auth_token, test_sos):
        """Test saga cancellation flow."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Trigger SOS
        response = await http_client.post(
            f"{service_urls['sos']}/sos",
            json=test_sos,
            headers=headers
        )
        assert response.status_code == 201
        incident_id = response.json()["incident_id"]

        # Wait for dispatch to process
        await asyncio.sleep(2)

        # Cancel the incident
        response = await http_client.post(
            f"{service_urls['sos']}/sos/{incident_id}/cancel",
            headers=headers
        )
        assert response.status_code == 200

        # Wait for cancellation to propagate
        await asyncio.sleep(2)

        # Check analytics captured cancellation
        response = await http_client.get(f"{service_urls['analytics']}/stats/events")
        assert response.status_code == 200

        events = response.json()
        assert events.get("sos.cancelled", 0) >= 1

    @pytest.mark.asyncio
    async def test_multiple_concurrent_incidents(self, http_client, service_urls, auth_token):
        """Test handling multiple concurrent incidents."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Trigger multiple incidents
        incidents = []
        for i in range(3):
            sos_data = {
                "lat": 37.7749 + i * 0.01,  # Slightly different locations
                "lon": -122.4194 + i * 0.01,
                "mode": "online"
            }

            response = await http_client.post(
                f"{service_urls['sos']}/sos",
                json=sos_data,
                headers=headers
            )
            assert response.status_code == 201
            incidents.append(response.json()["incident_id"])

        # Wait for all sagas to complete
        await asyncio.sleep(5)

        # Check analytics captured all events
        response = await http_client.get(f"{service_urls['analytics']}/stats/events")
        assert response.status_code == 200

        events = response.json()
        assert events.get("sos.triggered", 0) >= 3

        # Verify all incidents exist
        for incident_id in incidents:
            response = await http_client.get(f"{service_urls['sos']}/sos/{incident_id}")
            assert response.status_code == 200


class TestStrategyPatterns:
    """Test different responder matching strategies."""

    @pytest.mark.asyncio
    async def test_nearest_matcher_strategy(self, http_client, service_urls, auth_token):
        """Test nearest neighbor matching strategy."""
        # This would require setting MATCHER=nearest and having test responders
        # For now, just verify the service can handle the request
        headers = {"Authorization": f"Bearer {auth_token}"}

        sos_data = {
            "lat": 37.7749,
            "lon": -122.4194,
            "mode": "online"
        }

        response = await http_client.post(
            f"{service_urls['sos']}/sos",
            json=sos_data,
            headers=headers
        )
        assert response.status_code == 201

        # Wait for processing
        await asyncio.sleep(2)

        # Check that dispatch service processed it (analytics would show events)
        response = await http_client.get(f"{service_urls['analytics']}/stats/events")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_round_robin_strategy(self, http_client, service_urls, auth_token):
        """Test round-robin matching strategy."""
        # Would need to set MATCHER=round_robin environment variable
        # This is a placeholder for the test structure
        headers = {"Authorization": f"Bearer {auth_token}"}

        sos_data = {
            "lat": 37.7749,
            "lon": -122.4194,
            "mode": "online"
        }

        response = await http_client.post(
            f"{service_urls['sos']}/sos",
            json=sos_data,
            headers=headers
        )
        assert response.status_code == 201


class TestCircuitBreaker:
    """Test circuit breaker functionality under failure conditions."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, http_client, service_urls, auth_token):
        """Test that services recover after temporary failures."""
        # This is difficult to test without injecting failures
        # For now, verify normal operation works
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Trigger several incidents to test circuit breaker state
        for i in range(3):
            sos_data = {
                "lat": 37.7749,
                "lon": -122.4194,
                "mode": "online"
            }

            response = await http_client.post(
                f"{service_urls['sos']}/sos",
                json=sos_data,
                headers=headers
            )
            assert response.status_code == 201

            # Small delay between requests
            await asyncio.sleep(0.5)

        # Wait for processing
        await asyncio.sleep(3)

        # Verify system is still responsive
        response = await http_client.get(f"{service_urls['user']}/healthz")
        assert response.status_code == 200


class TestAnalyticsAggregation:
    """Test analytics service event aggregation."""

    @pytest.mark.asyncio
    async def test_event_aggregation(self, http_client, service_urls, auth_token):
        """Test that analytics aggregates events correctly."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Trigger multiple incidents
        initial_count = 0
        try:
            response = await http_client.get(f"{service_urls['analytics']}/stats/events")
            initial_stats = response.json()
            initial_count = initial_stats.get("sos.triggered", 0)
        except:
            pass  # Analytics might be empty initially

        # Trigger incidents
        for i in range(2):
            sos_data = {
                "lat": 37.7749 + i * 0.01,
                "lon": -122.4194 + i * 0.01,
                "mode": "online"
            }

            response = await http_client.post(
                f"{service_urls['sos']}/sos",
                json=sos_data,
                headers=headers
            )
            assert response.status_code == 201

        # Wait for aggregation
        await asyncio.sleep(4)

        # Check final counts
        response = await http_client.get(f"{service_urls['analytics']}/stats/events")
        assert response.status_code == 200

        final_stats = response.json()
        final_count = final_stats.get("sos.triggered", 0)

        # Should have increased by at least the number of incidents triggered
        assert final_count >= initial_count + 2

    @pytest.mark.asyncio
    async def test_zone_analytics(self, http_client, service_urls, auth_token):
        """Test zone-based analytics."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Trigger incident in specific location
        sos_data = {
            "lat": 37.7749,
            "lon": -122.4194,
            "mode": "online"
        }

        response = await http_client.post(
            f"{service_urls['sos']}/sos",
            json=sos_data,
            headers=headers
        )
        assert response.status_code == 201

        # Wait for processing
        await asyncio.sleep(3)

        # Check zone stats
        response = await http_client.get(f"{service_urls['analytics']}/stats/zones")
        assert response.status_code == 200

        zones = response.json()
        assert isinstance(zones, list)
        # Should contain zone data if dispatch processed the incident