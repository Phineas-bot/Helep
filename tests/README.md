# HELEP Integration Tests

This directory contains integration tests for the HELEP microservices platform.

## Test Structure

- `conftest.py`: Shared test fixtures and configuration
- `test_smoke.py`: Basic health checks and API functionality tests
- `test_saga.py`: End-to-end saga flow tests
- `requirements.txt`: Test dependencies

## Running Tests Locally

### Prerequisites

- Docker and docker-compose
- Python 3.11+
- All services running via docker-compose

### Setup

1. Start the services:
```bash
docker compose -f docker-compose.dev.yml up --build
```

2. In another terminal, install test dependencies:
```bash
pip install -r tests/requirements.txt
```

3. Run the tests:
```bash
# Run all tests
pytest tests/

# Run smoke tests only
pytest tests/test_smoke.py -v

# Run saga tests only
pytest tests/test_saga.py -v

# Run with coverage
pytest tests/ --cov=services --cov-report=html
```

## Test Categories

### Smoke Tests (`test_smoke.py`)

Basic functionality tests that verify:
- All services are healthy (liveness/readiness probes)
- User registration and authentication work
- Basic API endpoints respond correctly
- Prometheus metrics are exposed

### Saga Tests (`test_saga.py`)

End-to-end tests that verify the complete incident flow:
- SOS trigger starts the saga
- Dispatch service assigns responders
- Notification service sends alerts
- Analytics service aggregates events
- Cancellation flow works
- Multiple concurrent incidents are handled
- Circuit breaker recovers from failures

## CI/CD Integration

Tests are automatically run in GitHub Actions as part of the CI pipeline:

1. **Validate job**: Syntax and Helm linting
2. **Test job**: Integration tests with local Kafka
3. **Build job**: Docker image building
4. **Deploy job**: Kubernetes deployment

The test job uses:
- Local Kafka service in GitHub Actions
- Python services started with uvicorn
- pytest with asyncio support
- Coverage reporting

## Test Configuration

Tests use the following configuration:
- Service URLs: localhost:8001-8005
- Kafka bootstrap: localhost:9092
- Test user: `+237600000001` / `testpass123`
- Test timeout: 10 seconds per request
- Service startup wait: 30 seconds max

## Troubleshooting

### Services not ready
If tests fail with connection errors:
```bash
# Check service logs
docker compose -f docker-compose.dev.yml logs

# Check service health
curl localhost:8001/healthz
curl localhost:8001/readyz
```

### Kafka connection issues
```bash
# Check Kafka topics
docker exec helep-kafka-1 kafka-topics.sh --bootstrap-server localhost:9092 --list

# Check Kafka logs
docker compose -f docker-compose.dev.yml logs kafka
```

### Test timeouts
Increase timeout in conftest.py or check service performance.

## Adding New Tests

### For new endpoints:
1. Add test to appropriate file (`test_smoke.py` for basic, `test_saga.py` for flows)
2. Use existing fixtures (`http_client`, `auth_token`, `service_urls`)
3. Follow async/await pattern for HTTP calls

### For new services:
1. Add service URL to `service_urls` fixture
2. Add health checks to `TestServiceHealth` class
3. Add basic functionality tests to `TestBasicFunctionality` class

## Coverage

Tests aim for:
- API endpoint coverage (all routes tested)
- Saga flow coverage (complete incident lifecycle)
- Error condition coverage (auth failures, invalid data)
- Integration coverage (service-to-service communication)