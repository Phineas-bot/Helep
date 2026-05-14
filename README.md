# HELEP: Cloud-Native Emergency Response Platform

**Student Name:** NGNINDEM PHINEES  
**Student ID:** ICTU20234200  
**Course:** Software Architecture  
**Date:** May 14, 2026  

---

## Abstract

HELEP represents a comprehensive implementation of a cloud-native emergency response platform, demonstrating advanced software architecture principles in a distributed microservices context. The system enables real-time incident coordination between citizens, emergency responders, and police through event-driven communication patterns. This project showcases the practical application of enterprise architecture patterns including choreographed sagas, circuit breaker fault tolerance, and repository abstractions, deployed using Kubernetes orchestration and Helm packaging. The implementation includes complete CI/CD pipelines, comprehensive testing suites, and production-ready monitoring infrastructure.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Local Development](#local-development)
- [Testing Strategy](#testing-strategy)
- [Production Deployment](#production-deployment)
- [Documentation](#documentation)
- [References](#references)

---

```
helep/
├── Lecture Notes Software Architecture Orchestration with K8s Mini Project Specifications.pdf   ← read this first
├── architecture-overview.md                   ← lecturer reference (not given to student)
├── design-process-template.md                 ← Part G: completed design document
├── patterns-template.md                       ← Part H: completed patterns document
├── DEMO-SCRIPT.md                             ← Demo video script and instructions
├── DEPLOYMENT.md                              ← Production deployment guide
├── SECRETS.md                                 ← Security and secrets management guide
├── docker-compose.dev.yml                     ← dev environment with all services
├── docker-compose.override.yml                ← optional dev overrides
├── pytest.ini                                 ← test configuration
├── tests/                                     ← integration test suite
│   ├── conftest.py
│   ├── test_smoke.py
│   ├── test_saga.py
│   └── README.md
├── charts/helep/                              ← Helm umbrella chart
├── k8s/infra/                                 ← Kubernetes infrastructure manifests
├── .github/workflows/ci-cd.yml                ← GitHub Actions CI/CD pipeline
└── services/
    ├── user-service/         (port 8001, FastAPI)
    ├── sos-service/          (port 8002)
    ├── dispatch-service/     (port 8003)
    ├── notification-service/ (port 8004)
    └── analytics-service/    (port 8005)
```

## What's implemented (deliverables completed ✅)

### Core Architecture
- **5 microservices** with FastAPI, SQLite, and Kafka integration
- **Event-driven saga** pattern for incident coordination
- **Circuit breaker** with three-state machine (CLOSED→OPEN→HALF_OPEN)
- **Strategy pattern** for responder matching (Nearest, Credibility, RoundRobin)
- **Repository pattern** for data access abstraction

### Infrastructure & Deployment
- **Dockerfiles** for all 5 services with multi-stage builds
- **Helm umbrella chart** with parameterized Kubernetes manifests
- **Strimzi Kafka cluster** with 7 application topics
- **Prometheus/Grafana monitoring** stack with ServiceMonitors and dashboards
- **GitHub Actions CI/CD** pipeline (validate → test → build → deploy)

### Testing & Quality Assurance
- **Integration test suite** with smoke tests and saga end-to-end tests
- **Health checks** (liveness/readiness probes) on all services
- **Prometheus metrics** exposure for monitoring
- **Structured logging** with JSON output

### Documentation & Demos
- **Design document** (`design-process-template.md`) - architectural decisions and trade-offs
- **Patterns document** (`patterns-template.md`) - code-level pattern implementations
- **Demo script** (`DEMO-SCRIPT.md`) - video recording guide and automated demo
- **Deployment guide** (`DEPLOYMENT.md`) - production operations manual
- **Secrets guide** (`SECRETS.md`) - security best practices

## Quick local development

### Start all services:
```bash
docker compose -f docker-compose.dev.yml up --build
```

### Test basic functionality:
```bash
# Register a user
curl -X POST localhost:8001/signup \
  -H 'content-type: application/json' \
  -d '{"phone":"+237600000001","password":"hunter22","role":"citizen"}'

# Get JWT token from response, then trigger SOS
curl -X POST localhost:8002/sos \
  -H "Authorization: Bearer <token>" \
  -H 'content-type: application/json' \
  -d '{"lat":37.7749,"lon":-122.4194,"mode":"online"}'
```

### Run integration tests:
```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run all tests
pytest tests/
```

## Production deployment

### Prerequisites:
- Kubernetes 1.24+
- Helm 3.10+
- Strimzi Operator

### Deploy:
```bash
# Create namespaces and Kafka
kubectl apply -f k8s/infra/

# Deploy services
helm upgrade --install helep charts/helep -n helep
```

See `DEPLOYMENT.md` for detailed production setup and operations guide.

## Architecture overview

HELEP implements a **choreographed saga** across 5 microservices:

1. **user-service**: Identity management with JWT authentication
2. **sos-service**: Incident triggering and cancellation
3. **dispatch-service**: Responder matching using configurable strategies
4. **notification-service**: Multi-channel delivery simulation
5. **analytics-service**: Event aggregation for police dashboard

All services communicate via **Apache Kafka** with partitioned topics ensuring ordered event processing. The system includes comprehensive **resiliency patterns**: circuit breakers, graceful shutdown, health checks, and resource limits.

## Key patterns implemented

- **Saga (Choreographed)**: Event-driven incident coordination
- **Pub/Sub**: Kafka-based service communication
- **Repository**: Data access abstraction
- **Strategy**: Pluggable matching algorithms
- **Outbox-lite**: Event publishing after DB commits
- **Circuit Breaker**: Fault tolerance for Kafka operations
- **Health Check**: Kubernetes probe patterns
- **Graceful Shutdown**: Clean termination with connection draining

## Testing strategy

- **Smoke tests**: Health checks, basic API functionality, metrics exposure
- **Saga tests**: End-to-end incident flows, concurrent incidents, cancellation
- **CI integration**: Automated testing with local Kafka in GitHub Actions
- **Coverage**: API endpoints, saga flows, error conditions, service integration

## References

1. Richardson, C. (2018). *Microservices Patterns: With examples in Java*. Manning Publications.

2. Fowler, M. (2003). *Patterns of Enterprise Application Architecture*. Addison-Wesley.

3. Evans, E. (2003). *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Addison-Wesley.

4. Apache Kafka Documentation. (2023). Retrieved from https://kafka.apache.org/documentation/

5. Kubernetes Documentation. (2023). Retrieved from https://kubernetes.io/docs/

6. Helm Documentation. (2023). Retrieved from https://helm.sh/docs/

7. FastAPI Documentation. (2023). Retrieved from https://fastapi.tiangolo.com/

---

*This project demonstrates the application of software architecture principles in building scalable, reliable distributed systems for critical emergency response scenarios.*

## Demo video

A complete demo script is provided in `DEMO-SCRIPT.md` with:
- 5-7 minute video outline
- Terminal commands and expected outputs
- Architecture diagram overlays
- Automated demo script option
- Recording tips and best practices

The demo covers:
- Architecture overview
- Local development setup
- User registration and authentication
- SOS incident triggering
- Responder dispatch and assignment
- Notification delivery
- Analytics dashboard
- System health and monitoring
- Kubernetes deployment
TOKEN=...
curl -X POST localhost:8002/sos -H "authorization: Bearer $TOKEN" \
     -H 'content-type: application/json' \
     -d '{"lat":4.0500,"lon":9.7700,"mode":"online"}'
# tail notification-service logs to see the simulated SMS line:
docker compose -f docker-compose.dev.yml logs -f notification-service
# police stats:
curl localhost:8005/stats/events
curl localhost:8005/stats/zones
```

If the saga works in compose, the K8s version is just packaging.

## Production assets added

- `charts/helep/` now renders the app deployment stack, optional ingress, PVCs, HPA, network policy, Prometheus `ServiceMonitor`s, a raw Prometheus scrape-config ConfigMap, and a Grafana dashboard ConfigMap.
- `k8s/infra/` contains the Strimzi Kafka cluster manifest, topic CRs, and namespaces for `kafka`, `monitoring`, and `helep`.
- `.github/workflows/ci-cd.yml` validates Python and Helm, builds and pushes service images to GHCR, applies Kafka infra, and deploys the Helm release.

For local Helm testing:

```bash
helm template helep charts/helep -f charts/helep/values.dev.yaml
```

## Submission

See **Section "Submission"** of the brief. https://forms.gle/9QCvLTMV3CSZpxPc8.
