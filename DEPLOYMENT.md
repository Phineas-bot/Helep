# HELEP Deployment & Operational Guide

This document describes the production-ready infrastructure, Kubernetes deployment, and operational patterns for the HELEP microservices platform.

## Architecture Overview

HELEP is a cloud-native microservices application designed for Kubernetes. It consists of five Python FastAPI services coordinated via Apache Kafka, with comprehensive monitoring and graceful shutdown handling.

### Services

| Service | Port | Purpose | Key Operations |
|---------|------|---------|-----------------|
| **user-service** | 8001 | Identity, JWT auth, credibility | Signup, login, contact management |
| **sos-service** | 8002 | SOS incident triggering | Trigger incident, cancel, retrieve |
| **dispatch-service** | 8003 | Saga coordinator, responder matching | Strategy pattern matching, assignment |
| **notification-service** | 8004 | Event sink, notification delivery | Template-driven SMS/push simulation |
| **analytics-service** | 8005 | Event aggregation, statistics | Event counting, zone/crime analytics |

### Key Technology Stack

- **Runtime**: Python 3.11+, FastAPI, uvicorn
- **Messaging**: Apache Kafka 3.7.0 via Strimzi Operator
- **Persistence**: SQLite (per-service), auto-migration on startup
- **Security**: bcrypt (password hashing), PyJWT (bearer tokens), env-var secrets
- **Observability**: structlog (JSON logs), Prometheus metrics, Grafana dashboards
- **Orchestration**: Kubernetes (via Helm v3), Strimzi Kafka Operator
- **Container Registry**: GitHub Container Registry (GHCR)

## Helm Deployment

### Prerequisites

- Kubernetes 1.24+
- Helm 3.10+
- Strimzi Operator 0.30+ (for Kafka cluster management)
- Prometheus + Grafana (optional, for monitoring)

### Local Development Deployment

```bash
# Create namespaces
kubectl apply -f k8s/infra/namespaces.yaml

# Deploy Kafka infrastructure
kubectl apply -f k8s/infra/kafka-cluster.yaml
kubectl apply -f k8s/infra/kafka-topics.yaml

# Wait for Kafka to be ready
kubectl wait --for=condition=Ready KafkaCluster/kafka -n kafka --timeout=300s

# Deploy services with dev values
helm upgrade --install helep charts/helep \
  --namespace helep \
  --values charts/helep/values.dev.yaml

# Monitor deployment
kubectl get pods -n helep -w
```

### Production Deployment

```bash
# Create namespaces
kubectl apply -f k8s/infra/namespaces.yaml

# Deploy Kafka infrastructure with production configuration
kubectl apply -f k8s/infra/kafka-cluster.yaml
kubectl apply -f k8s/infra/kafka-topics.yaml

# Deploy services with production overrides
helm upgrade --install helep charts/helep \
  --namespace helep \
  --values charts/helep/values.yaml \
  --set global.imagePullPolicy=Always \
  --set-string global.imagePullSecrets[0].name=ghcr-credentials \
  --set services.user-service.image.repository=ghcr.io/owner/helep-user-service \
  --set services.user-service.image.tag=v1.0.0 \
  ... (repeat for all services)
```

## Helm Configuration

### Global Values

```yaml
global:
  imagePullPolicy: IfNotPresent      # Set to Always for production
  imagePullSecrets: []               # Add credentials for private registries

defaultResources:
  requests:
    memory: "64Mi"                   # Baseline allocation
    cpu: "50m"
  limits:
    memory: "256Mi"                  # Hard limit
    cpu: "500m"

monitoring:
  enabled: true                      # Enable Prometheus ServiceMonitor
  grafana:
    dashboardLabel: grafana_dashboard
```

### Per-Service Configuration

Each service can be customized via `values.yaml`:

```yaml
services:
  user-service:
    image:
      repository: helep_user-service
      tag: latest
    replicaCount: 1                  # Pod replicas
    service:
      port: 8001
    persistence:
      enabled: true
      size: 100Mi                    # PVC size for SQLite DB
    ingress:
      enabled: false
      host: ""                       # Set to FQDN for production
    hpa:
      minReplicas: 1
      maxReplicas: 3
      cpuUtilization: 60             # HPA trigger threshold
    networkPolicy:
      enabled: false                 # Enable for production
    resources: {}                    # Inherits defaultResources
    terminationGracePeriodSeconds: 30 # Graceful shutdown window
```

### Development Overrides (values.dev.yaml)

```yaml
monitoring:
  enabled: false                     # Reduce load for local testing

services:
  <service-name>:
    image:
      tag: latest                    # Use local docker-compose images
    env:
      KAFKA_BOOTSTRAP: kafka:9092    # In-cluster Kafka address
      DB_PATH: /data/<service>.db
```

## Graceful Shutdown

### Configuration

- **terminationGracePeriodSeconds**: 30 seconds (configurable per service in values.yaml)
- Each service has FastAPI `@app.on_event("shutdown")` handler that:
  - Closes Kafka producer (flushing pending messages)
  - Stops consumer group (completing in-flight events)
  - Gracefully closes database connections

### Kubernetes Flow

1. Pod receives `SIGTERM` signal
2. Kubernetes waits up to `terminationGracePeriodSeconds` (30s default)
3. FastAPI calls registered shutdown handlers (`app.on_event("shutdown")`)
4. Connections close cleanly, pending events flush
5. Process exits
6. Pod is removed from service endpoints

### Best Practices

- **Load Balancer**: Drain in-flight connections via graceful shutdown callbacks
- **Database**: Use connection pooling with proper close() semantics
- **Kafka**: Set `linger.ms` to batch pending messages before shutdown
- **Monitoring**: Track shutdown duration via metrics or logs

## Health Checks

### Liveness Probe (livenessProbe)

- **Endpoint**: `GET /healthz`
- **Frequency**: Every 10 seconds
- **Timeout**: 5 seconds
- **Failure Threshold**: 3 failures → pod restart
- **Purpose**: Detect dead/hung processes

### Readiness Probe (readinessProbe)

- **Endpoint**: `GET /readyz`
- **Frequency**: Every 5 seconds
- **Timeout**: 3 seconds
- **Failure Threshold**: 2 failures → pod removed from service
- **Purpose**: Detect temporary unavailability (e.g., Kafka broker down)

### Implementation in Services

```python
@app.get("/healthz")
async def healthz():
    """Liveness: process is alive."""
    return {"status": "ok"}

@app.get("/readyz")
async def readyz():
    """Readiness: Kafka and database are reachable."""
    if not await health():  # checks Kafka producer connectivity
        raise HTTPException(503, "kafka unreachable")
    return {"status": "ready"}
```

## Circuit Breaker Pattern

### Implementation

All services implement a three-state circuit breaker for Kafka producer calls:

**States:**
- **CLOSED**: Normal operation, requests succeed. Transitions to OPEN on failure threshold.
- **OPEN**: Broken state, requests fail-fast (return False). Waits for `reset_after_s` (default 10s).
- **HALF_OPEN**: Recovery probe state. Allows one request through to test recovery.

**Configuration:**
```python
circuit_breaker = CircuitBreaker(
    fail_threshold=5,        # Open after 5 consecutive failures
    reset_after_s=10.0       # Retry after 10 seconds
)

if circuit_breaker.allow():
    try:
        await producer.send("topic", value=data, key=incident_id)
        circuit_breaker.record_success()
    except Exception:
        circuit_breaker.record_failure()
else:
    log.warning("circuit_open", topic="topic")
    # Handle downstream (queue locally, return error to client, etc.)
```

### Benefits

- Prevents cascading failures across services
- Fast fail when dependencies are unavailable
- Automatic recovery without external intervention
- Reduces load on failing dependencies

## Kafka Cluster

### Strimzi Operator Setup

The Kafka cluster is provisioned via Strimzi Operator CRDs:

```bash
# Install Strimzi Operator (if not already in cluster)
helm repo add strimzi https://strimzi.io/charts
helm install strimzi-operator strimzi/strimzi-kafka-operator -n kafka --create-namespace

# Deploy cluster and topics
kubectl apply -f k8s/infra/kafka-cluster.yaml
kubectl apply -f k8s/infra/kafka-topics.yaml
```

### Cluster Configuration (kafka-cluster.yaml)

- **Brokers**: 3 replicas (high availability)
- **Storage**: 10Gi per broker (persistent volume)
- **Kraft Mode**: Enabled (simplified metadata management, no ZooKeeper dependency)
- **Auto Topic Creation**: Disabled (explicit KafkaTopic CRDs required)

### Topics

Seven application topics (3 partitions, 3 replicas each):

| Topic | Purpose | Payload |
|-------|---------|---------|
| `user.registered` | User signup event | `{user_id, phone, role}` |
| `sos.triggered` | Incident created | `{incident_id, user_id, lat, lon, mode}` |
| `sos.cancelled` | Incident cancelled | `{incident_id}` |
| `responder.assigned` | Responder matched | `{assignment_id, responder_id, incident_id}` |
| `responder.confirmed` | Responder accepts | `{assignment_id, status}` |
| `safety.zone.entered` | Responder geofence | `{responder_id, zone_id}` |
| `notification.sent` | Notification delivered | `{template_id, channel, recipient}` |

### Consumer Group Coordination

Partition keying by `incident_id` ensures:
- All events for an incident go to the same partition
- Consumer group preserves ordering within incident lifecycle
- Dispatch-service idempotency checks prevent double-assignment

## Monitoring & Observability

### Prometheus Metrics

Each service exports Prometheus metrics on `/metrics`:

```
# Counter examples
helep_user_signups_total{service="user-service"}
helep_user_logins_total{service="user-service"}
helep_sos_triggers_total{service="sos-service", mode="online|offline"}
helep_sos_cancels_total{service="sos-service"}

# Histogram/Gauge (via prometheus-client)
http_requests_total{endpoint="/signup", method="POST", status="201"}
```

### Grafana Dashboard

A pre-built Grafana dashboard (ConfigMap: `helep-grafana-dashboard`) includes panels for:

- Service availability (uptime, probe failures)
- Request volume (signup, SOS triggers, assignments)
- Error rates (4xx, 5xx, Kafka failures)
- Incident flow (triggered → assigned → notifications)
- Responder metrics (assignments, zone entries)

### ServiceMonitor CRDs

Prometheus operator discovers metrics via ServiceMonitor CRs:

```yaml
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: helep-user-service
spec:
  selector:
    matchLabels:
      app: helep-user-service
  endpoints:
  - port: http
    path: /metrics
```

## CI/CD Pipeline

### GitHub Actions Workflow (.github/workflows/ci-cd.yml)

**Stages:**

1. **Validate**
   - Python syntax check (all services/)
   - Helm chart lint (charts/helep/)

2. **Build & Push**
   - Matrix job (per service)
   - Build Docker image from Dockerfile
   - Push to GHCR (ghcr.io/<owner>/helep-<service>:<sha>)
   - Also tag as `:latest`

3. **Deploy**
   - Set kubeconfig from GitHub Secret (`KUBE_CONFIG_B64`)
   - `kubectl apply k8s/infra/*` (infrastructure)
   - `helm upgrade --install` with image tag overrides

### Triggering Deployment

- **On PR**: Validate + Build (push to GHCR) only
- **On merge to main**: Validate + Build + Deploy

### Required Secrets

Set in GitHub repository settings:

```
KUBE_CONFIG_B64 = <base64-encoded kubeconfig>
GHCR_TOKEN = <GitHub Container Registry token>
```

## Operational Runbooks

### Scale a Service

```bash
# Increase replicas
helm upgrade helep charts/helep \
  --set services.user-service.replicaCount=5 \
  -n helep

# Or edit directly
kubectl scale deployment helep-user-service -n helep --replicas=5
```

### Update Image Tag

```bash
helm upgrade helep charts/helep \
  --set services.user-service.image.tag=v1.1.0 \
  -n helep
```

### Drain a Pod Gracefully

```bash
# Terminates pod after terminationGracePeriodSeconds (default 30s)
kubectl delete pod helep-user-service-xyz -n helep --grace-period=30
```

### View Logs

```bash
# Real-time logs (JSON structured logs from structlog)
kubectl logs -f deployment/helep-user-service -n helep

# Previous pod (if crashed)
kubectl logs --previous deployment/helep-user-service -n helep

# All pods in namespace
kubectl logs -f -l app=helep-user-service --all-containers=true -n helep
```

### Restart a Service

```bash
# Rolling restart (zero downtime)
kubectl rollout restart deployment/helep-user-service -n helep

# Check rollout status
kubectl rollout status deployment/helep-user-service -n helep
```

### Access a Pod Shell

```bash
kubectl exec -it deployment/helep-user-service -n helep -- /bin/bash
```

## Environment Variables

Each service is configured via environment variables (from ConfigMap and Secret):

### Configuration (ConfigMap)

```
SERVICE_PORT=8001           # HTTP listen port
KAFKA_BOOTSTRAP=kafka:9092  # Kafka broker(s), comma-separated
DB_PATH=/data/user.db       # SQLite file path
MATCHER=NearestMatcher      # [dispatch-service only] Strategy: NearestMatcher | CredibilityWeightedMatcher
```

### Secrets (Secret)

```
JWT_SECRET=<random-string>  # JWT signing key for bearer tokens
```

### Best Practices

- **Never hardcode secrets** in ConfigMap; always use Secret objects
- **Rotate secrets** without pod restart by updating Secret and triggering rollout restart
- **Use external secrets operator** (ESO) for production to sync secrets from Vault/Azure Key Vault
- **Limit secret scope** via RBAC; pods should only access their own secrets

## Persistent Storage

Each service has optional SQLite database storage:

```yaml
persistence:
  enabled: true      # Mount PVC at /data
  size: 100Mi        # Default size (override as needed)
```

### PVC Details

- **Access Mode**: ReadWriteOnce (single pod)
- **Storage Class**: Default (cluster-dependent)
- **Lifecycle**: Persists across pod restarts; deleted with Helm uninstall

### Database Auto-Migration

On startup, each service's `db.py` initializes tables:

```python
def init() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (...)""")
    conn.commit()
    conn.close()
```

## Auto-Scaling (HPA)

Each service has a HorizontalPodAutoscaler:

```yaml
hpa:
  minReplicas: 1
  maxReplicas: 3
  cpuUtilization: 60  # Target 60% CPU usage
```

### Behavior

- Kubernetes monitors average CPU per pod
- If average > 60%, adds a new pod (up to maxReplicas)
- If average < 60% for cooldown period, removes a pod (down to minReplicas)
- Requires metrics-server running in kube-system namespace

## Security Considerations

### Network Policies

Optional NetworkPolicy CRs (set `networkPolicy.enabled: true` in values):

```yaml
ingress:
- from:
  - podSelector: {}  # Allow traffic from any pod in namespace
  ports:
  - protocol: TCP
    port: 8001
```

### RBAC

Each service pod uses the default service account. For production:

```bash
# Create per-service service accounts
kubectl create serviceaccount helep-user-service -n helep
kubectl create serviceaccount helep-sos-service -n helep
# ... etc

# Bind to deployments in values.yaml (optional)
# Add: serviceAccountName: helep-user-service
```

### Image Registry Credentials

For private registries (e.g., private GHCR repo):

```bash
# Create image pull secret
kubectl create secret docker-registry ghcr-credentials \
  --docker-server=ghcr.io \
  --docker-username=<token> \
  --docker-password=<token> \
  -n helep

# Reference in values.yaml
global:
  imagePullSecrets:
  - name: ghcr-credentials
```

## Troubleshooting

### Pod stuck in CrashLoopBackOff

```bash
# Check logs
kubectl logs <pod-name> -n helep

# Likely causes:
# - Database initialization failure (check DB_PATH, permissions)
# - Kafka bootstrap connection failure (check KAFKA_BOOTSTRAP env var)
# - Port already in use (check SERVICE_PORT)
```

### Service not receiving traffic

```bash
# Check readiness probe
kubectl get pod <pod-name> -n helep -o jsonpath='{.status.conditions[?(@.type=="Ready")]}'

# If not Ready, check probe logs
kubectl logs <pod-name> -n helep | grep readyz

# Check service endpoints
kubectl get endpoints <service-name> -n helep
```

### High CPU usage

```bash
# Check resource requests/limits
kubectl describe pod <pod-name> -n helep

# Monitor real-time usage
kubectl top pod <pod-name> -n helep

# Increase limits if needed
helm upgrade helep charts/helep \
  --set services.user-service.resources.limits.cpu=1000m \
  -n helep
```

### Kafka topics not consumed

```bash
# Verify topics exist
kubectl exec -it kafka-0 -n kafka -- bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# Check consumer group lag
kubectl exec -it kafka-0 -n kafka -- bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group dispatch-service --describe
```

## References

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [Strimzi Operator](https://strimzi.io/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Prometheus](https://prometheus.io/)
