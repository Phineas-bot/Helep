# HELEP Environment Variables & Secrets Guide

This guide explains how environment variables are configured in HELEP, with emphasis on secrets management and security best practices.

## Environment Variable Categories

### Configuration (Non-Sensitive)

These variables configure application behavior and are stored in ConfigMaps:

| Variable | Example | Service | Purpose |
|----------|---------|---------|---------|
| `SERVICE_PORT` | `8001` | All | HTTP listen port |
| `KAFKA_BOOTSTRAP` | `kafka:9092` | All | Kafka broker(s) |
| `DB_PATH` | `/data/user.db` | All | SQLite database path |
| `MATCHER` | `NearestMatcher` | dispatch-service | Responder matching strategy |

### Secrets (Sensitive)

These variables contain sensitive data and are stored in Secret objects:

| Variable | Example | Service | Purpose | Rotation |
|----------|---------|---------|---------|----------|
| `JWT_SECRET` | `<random-32-char>` | All | JWT signing key | Monthly |
| `KAFKA_BOOTSTRAP` | `kafka+ssl://...` | All | Secure Kafka broker (optional) | On broker cert update |

## Kubernetes Deployment Configuration

### ConfigMap Mounting (Configuration)

In `charts/helep/templates/configmaps.yaml`, configuration values are stored:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ printf "%s-%s-config" $.Release.Name $name }}
data:
  SERVICE_PORT: "{{ $svc.service.port }}"
  KAFKA_BOOTSTRAP: "{{ .Values.kafkaBootstrap | default "kafka:9092" }}"
  DB_PATH: "/data/{{ $name }}.db"
  {{- if eq $name "dispatch-service" }}
  MATCHER: "{{ .Values.matcher | default "NearestMatcher" }}"
  {{- end }}
```

### Secret Mounting (Secrets)

In `charts/helep/templates/secrets.yaml`, sensitive data is stored Base64-encoded:

```yaml
apiVersion: v1
kind: Secret
type: Opaque
metadata:
  name: {{ printf "%s-%s-secret" $.Release.Name $name }}
stringData:
  JWT_SECRET: {{ .Values.services[$name].secrets.jwtSecret | default "dev-only-change-me" | quote }}
```

### Deployment Env Vars

In `charts/helep/templates/deployments.yaml`, pods are configured to read both:

```yaml
env:
# From ConfigMap
- name: SERVICE_PORT
  valueFrom:
    configMapKeyRef:
      name: {{ printf "%s-%s-config" $.Release.Name $name }}
      key: SERVICE_PORT
- name: KAFKA_BOOTSTRAP
  valueFrom:
    configMapKeyRef:
      name: {{ printf "%s-%s-config" $.Release.Name $name }}
      key: KAFKA_BOOTSTRAP
- name: DB_PATH
  valueFrom:
    configMapKeyRef:
      name: {{ printf "%s-%s-config" $.Release.Name $name }}
      key: DB_PATH

# From Secret
- name: JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ printf "%s-%s-secret" $.Release.Name $name }}
      key: JWT_SECRET
```

## Development Workflow

### Local Development (docker-compose.dev.yml)

```yaml
services:
  user-service:
    build: ./services/user-service
    environment:
      SERVICE_PORT: "8001"
      KAFKA_BOOTSTRAP: "kafka:9092"      # Local Kafka container
      DB_PATH: "/data/user.db"
      JWT_SECRET: "dev-only-change-me"   # Hardcoded for dev-only
    volumes:
      - user-data:/data
```

**Note**: Development uses hardcoded secrets for convenience. **Never use in production.**

### Helm Deployment (values.dev.yaml)

For local Kubernetes testing:

```yaml
services:
  user-service:
    env:
      KAFKA_BOOTSTRAP: "kafka:9092"    # In-cluster Kafka address
      DB_PATH: "/data/user.db"
    secret:
      jwtSecret: "dev-only-change-me"  # Acceptable for dev cluster
```

### Helm Deployment (values.yaml - Production)

```yaml
services:
  user-service:
    env:
      KAFKA_BOOTSTRAP: "kafka:9092"    # Production Kafka address
      DB_PATH: "/data/user.db"
    secret:
      jwtSecret: ""                    # Must be set via helm --set or external values
```

**Deployment command:**

```bash
# Generate a secure random JWT_SECRET
JWT_SECRET=$(openssl rand -base64 32)

# Deploy with secret
helm upgrade --install helep charts/helep \
  -n helep \
  --set services.user-service.secret.jwtSecret="$JWT_SECRET" \
  --set services.sos-service.secret.jwtSecret="$JWT_SECRET" \
  ... (repeat for all services)
```

## Secret Rotation Workflow

### Scenario: Rotate JWT_SECRET Monthly

**Step 1: Generate new secret**

```bash
NEW_JWT_SECRET=$(openssl rand -base64 32)
echo "New JWT_SECRET: $NEW_JWT_SECRET"
```

**Step 2: Update Secret in Kubernetes**

```bash
kubectl patch secret helep-user-service-secret \
  -n helep \
  --type merge \
  -p '{"stringData":{"JWT_SECRET":"'$NEW_JWT_SECRET'"}}'

# Repeat for all services:
kubectl patch secret helep-sos-service-secret -n helep --type merge -p '{"stringData":{"JWT_SECRET":"'$NEW_JWT_SECRET'"}}'
kubectl patch secret helep-dispatch-service-secret -n helep --type merge -p '{"stringData":{"JWT_SECRET":"'$NEW_JWT_SECRET'"}}'
kubectl patch secret helep-notification-service-secret -n helep --type merge -p '{"stringData":{"JWT_SECRET":"'$NEW_JWT_SECRET'"}}'
kubectl patch secret helep-analytics-service-secret -n helep --type merge -p '{"stringData":{"JWT_SECRET":"'$NEW_JWT_SECRET'"}}'
```

**Step 3: Trigger pod restart**

```bash
# Rolling restart (zero downtime, pods pick up new secret)
kubectl rollout restart deployment/helep-user-service -n helep
kubectl rollout restart deployment/helep-sos-service -n helep
kubectl rollout restart deployment/helep-dispatch-service -n helep
kubectl rollout restart deployment/helep-notification-service -n helep
kubectl rollout restart deployment/helep-analytics-service -n helep

# Monitor rollout
kubectl rollout status deployment/helep-user-service -n helep
```

**Step 4: Verify**

```bash
# Check that pods have new restart count
kubectl get pods -n helep

# Verify by checking service health
curl -H "Authorization: Bearer <new-token>" localhost/me
```

## Production Secret Management Best Practices

### Option 1: External Secrets Operator (ESO)

Automatically sync secrets from external systems (Vault, Azure Key Vault, AWS Secrets Manager):

```yaml
# Install ESO helm chart (once per cluster)
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets-system --create-namespace

# Create SecretStore (points to external backend)
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-store
  namespace: helep
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "helep"

---
# Create ExternalSecret (syncs to k8s Secret)
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: helep-secrets
  namespace: helep
spec:
  refreshInterval: 1h                # Resync every hour
  secretStoreRef:
    name: vault-store
    kind: SecretStore
  target:
    name: helep-jwt-secret
    creationPolicy: Owner
  data:
  - secretKey: JWT_SECRET
    remoteRef:
      key: helep/jwt-secret
```

**Benefits:**
- Secrets never stored in Git
- Centralized rotation policy
- Audit trail in Vault
- Works across clusters

### Option 2: GitOps with Sealed Secrets

Encrypt secrets in Git using Sealed Secrets operator:

```bash
# Install sealed-secrets (once per cluster)
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/controller.yaml -n kube-system

# Encrypt a secret
echo -n mypassword | kubectl create secret generic mysecret --dry-run=client --from-file=password=/dev/stdin -o yaml | \
  kubeseal -f - > mysealedsecret.yaml

# Commit to Git
git add mysealedsecret.yaml
git commit -m "Add sealed secret"

# Deploy
kubectl apply -f mysealedsecret.yaml
```

**Benefits:**
- Encrypted secrets in Git repository
- Per-cluster encryption (can't decrypt on other clusters)
- GitOps-friendly

### Option 3: HashiCorp Vault

Centralized secret management with fine-grained policies:

```bash
# Write secret to Vault
vault write secret/helep/jwt JWT_SECRET=$(openssl rand -base64 32)

# Create Kubernetes auth role
vault write auth/kubernetes/role/helep \
  bound_service_account_names=helep-user-service \
  bound_service_account_namespaces=helep \
  policies=helep

# Pod authenticates via OIDC and reads secret
curl --header "Authorization: Bearer $VAULT_TOKEN" \
  https://vault.example.com/v1/secret/data/helep/jwt
```

**Benefits:**
- Enterprise-grade secret management
- Fine-grained RBAC
- Secret versioning and audit logs
- Encryption key rotation

## Application-Level Secrets Handling

### Python Service Best Practices

**Load secrets from environment (never hardcode):**

```python
import os

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET not set in environment")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")  # Optional, has default
```

**Validate secrets on startup:**

```python
@app.on_event("startup")
async def startup():
    if len(JWT_SECRET) < 32:
        log.warning("jwt_secret_weak", length=len(JWT_SECRET))
    log.info("service_starting", service="user-service", jwt_secret_length=len(JWT_SECRET))
```

**Never log secrets:**

```python
# ❌ WRONG
log.info("jwt_secret", secret=JWT_SECRET)

# ✅ CORRECT
log.info("jwt_secret_loaded", length=len(JWT_SECRET), hash=hashlib.sha256(JWT_SECRET.encode()).hexdigest()[:8])
```

**Use secrets in authentication:**

```python
def make_token(uid: str, role: str) -> str:
    payload = {
        "sub": uid,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e}")
```

## CI/CD Secret Injection

### GitHub Actions Secrets

Store secrets as GitHub Action secrets (not in repo):

```bash
# Go to repo Settings > Secrets and variables > Actions
# Add secrets:
# - JWT_SECRET
# - KUBE_CONFIG_B64
# - REGISTRY_TOKEN
```

### Workflow Secret Usage

```yaml
# .github/workflows/ci-cd.yml
deploy:
  runs-on: ubuntu-latest
  steps:
  - name: Login to GHCR
    uses: docker/login-action@v2
    with:
      registry: ghcr.io
      username: ${{ github.actor }}
      password: ${{ secrets.REGISTRY_TOKEN }}

  - name: Deploy with Helm
    env:
      JWT_SECRET: ${{ secrets.JWT_SECRET }}
    run: |
      helm upgrade --install helep charts/helep \
        --set services.user-service.secret.jwtSecret="$JWT_SECRET"
```

**Best Practices:**
- Scope secrets to specific workflows
- Use GitHub deployment environments for prod secrets
- Rotate CI/CD secrets quarterly
- Never echo secrets in logs

## Audit & Compliance

### Audit Secrets Access

```bash
# View secret access in Kubernetes audit logs
kubectl logs -n kube-system <kube-apiserver-pod> | grep "secrets" | jq '.'

# Verify no secrets in ConfigMaps (should only be in Secrets)
kubectl get configmaps -n helep -o json | jq '.items[].data | to_entries[]'
```

### Secret Lifecycle Policies

**Dev Environment:**
- Hardcoded secrets acceptable for speed
- Rotation: On-demand (developer decision)

**Staging Environment:**
- Vault or Sealed Secrets required
- Rotation: Monthly

**Production Environment:**
- External Secrets Operator + Vault mandatory
- Rotation: Monthly minimum, weekly recommended
- Audit logging: All secret reads/updates
- RBAC: Least-privilege (pods only read their own secrets)

## Troubleshooting

### Secret Not Available to Pod

```bash
# Check if secret exists
kubectl get secret helep-user-service-secret -n helep

# Check pod environment
kubectl exec -it deployment/helep-user-service -n helep -- env | grep JWT

# Check secret mounting in pod definition
kubectl get pod <pod-name> -n helep -o yaml | grep -A 20 "valueFrom"
```

### Invalid JWT Signature After Secret Rotation

```bash
# Problem: Old pods still using old JWT_SECRET
# Solution: Trigger pod restart

kubectl rollout restart deployment/helep-user-service -n helep
kubectl rollout status deployment/helep-user-service -n helep

# Verify all pods have restarted
kubectl get pods -n helep --sort-by=.metadata.managedFields[0].time
```

### Secret Data Too Large

```bash
# Kubernetes Secret max size: ~1MB
# If secrets exceed this, use external secrets operator or split into multiple secrets

kubectl get secret helep-user-service-secret -n helep -o json | jq '.data | to_entries | map(.value | length) | add'
```

## References

- [Kubernetes Secrets Documentation](https://kubernetes.io/docs/concepts/configuration/secret/)
- [External Secrets Operator](https://external-secrets.io/)
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [HashiCorp Vault](https://www.vaultproject.io/)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
