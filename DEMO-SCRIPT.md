# HELEP Demonstration Script

**Student Name:** NGNINDEM PHINEES  
**Student ID:** ICTU20234200  
**Course:** Software Architecture  
**Date:** May 14, 2026  

---

## Abstract

This demonstration script provides a structured guide for presenting the HELEP emergency response platform. The script outlines a 5-7 minute video demonstration covering system architecture, local development setup, and end-to-end functionality. The presentation showcases the practical implementation of microservices patterns, event-driven architecture, and cloud-native deployment practices developed during the capstone project.

---

## Video Specifications
- **Duration**: 5-7 minutes
- **Format**: MP4, 1080p resolution
- **Tools**: Screen recording software (OBS Studio), terminal emulator, web browser
- **Audience**: Capstone reviewers and faculty evaluators
- **Objective**: Demonstrate working system functionality and architectural implementation

---

## Script Outline

### [0:00-0:30] Introduction
**Visual**: HELEP logo/title screen, architecture diagram
**Narration**:
"Welcome to HELEP - a cloud-native emergency response platform built with microservices and event-driven architecture. In this demo, I'll show the complete system working end-to-end, from user registration through incident resolution."

### [0:30-1:30] Architecture Overview
**Visual**: Show architecture diagram, code structure
**Narration**:
"HELEP consists of 5 microservices:
- User service: Identity and authentication
- SOS service: Incident triggering
- Dispatch service: Intelligent responder matching
- Notification service: Multi-channel delivery
- Analytics service: Real-time statistics

All services communicate via Apache Kafka using a choreographed saga pattern. The system is containerized with Docker and orchestrated with Kubernetes via Helm."

**Show**: `tree services/`, `docker-compose.dev.yml`, `charts/helep/`

### [1:30-2:30] Local Development Setup
**Visual**: Terminal commands, docker-compose up
**Narration**:
"Let's start by running the system locally. We'll use docker-compose for development with local Kafka."

**Commands**:
```bash
cd /path/to/helep
docker compose -f docker-compose.dev.yml up --build
```

**Show**: Services starting, Kafka broker ready, health checks passing

### [2:30-3:30] User Registration & Authentication
**Visual**: Browser/Postman requests, database inspection
**Narration**:
"First, a citizen registers and logs in to get a JWT token."

**Demo**:
```bash
# Register user
curl -X POST localhost:8001/signup \
  -H 'content-type: application/json' \
  -d '{"phone":"+237600000001","password":"hunter22","role":"citizen"}'

# Login
curl -X POST localhost:8001/login \
  -H 'content-type: application/json' \
  -d '{"phone":"+237600000001","password":"hunter22"}'

# Get profile
curl -H "Authorization: Bearer <token>" localhost:8001/me
```

**Show**: User created, JWT returned, profile retrieved

### [3:30-4:30] SOS Incident Triggering
**Visual**: SOS trigger request, Kafka topic inspection
**Narration**:
"Now the citizen triggers an SOS incident. This starts the saga across services."

**Demo**:
```bash
# Trigger SOS
curl -X POST localhost:8002/sos \
  -H "Authorization: Bearer <token>" \
  -H 'content-type: application/json' \
  -d '{"lat":37.7749,"lon":-122.4194,"mode":"online"}'
```

**Show**: Incident created, `sos.triggered` event published to Kafka

### [4:30-5:30] Responder Dispatch & Assignment
**Visual**: Dispatch service logs, responder assignment
**Narration**:
"The dispatch service consumes the SOS event and matches a responder using the nearest-neighbor algorithm."

**Show**: Dispatch logs showing responder matching, `responder.assigned` event

**Demo**: Check dispatch service logs
```bash
docker logs helep_dispatch-service_1
```

### [5:30-6:30] Notification Delivery
**Visual**: Notification service logs, simulated delivery
**Narration**:
"The notification service delivers alerts to the assigned responder via SMS simulation."

**Show**: Notification logs, `notification.sent` event

### [6:30-7:00] Analytics Dashboard
**Visual**: Analytics endpoints, statistics
**Narration**:
"Finally, the analytics service aggregates all events for police monitoring."

**Demo**:
```bash
# Get event statistics
curl localhost:8005/stats/events

# Get zone statistics
curl localhost:8005/stats/zones
```

**Show**: Event counts, incident tracking

### [7:00-7:30] System Health & Scaling
**Visual**: Health endpoints, metrics
**Narration**:
"All services expose health checks and Prometheus metrics for monitoring."

**Demo**:
```bash
# Health checks
curl localhost:8001/healthz
curl localhost:8001/readyz

# Metrics
curl localhost:8001/metrics
```

### [7:30-8:00] Kubernetes Deployment
**Visual**: Helm commands, k8s dashboard
**Narration**:
"For production, we deploy to Kubernetes using our Helm umbrella chart."

**Demo** (if k8s available):
```bash
helm upgrade --install helep charts/helep -n helep
kubectl get pods -n helep
```

### [8:00-8:30] Conclusion
**Visual**: Architecture diagram, key metrics
**Narration**:
"HELEP demonstrates production-ready microservices with event-driven architecture, comprehensive monitoring, and graceful failure handling. The system successfully coordinates emergency response through reliable saga orchestration."

**Show**: Final statistics, clean shutdown

## Recording Tips

1. **Preparation**:
   - Pre-run all commands to ensure they work
   - Have JWT token ready
   - Clear terminal history between sections
   - Test all curl commands

2. **Pacing**:
   - Speak clearly and slowly
   - Pause after each command to show output
   - Use transitions between sections

3. **Visual Quality**:
   - Use high contrast terminal theme
   - Zoom in on important output
   - Show both terminal and browser if possible
   - Include architecture diagrams as overlays

4. **Audio**:
   - Use external microphone
   - Record in quiet environment
   - Add background music subtly if desired

## Alternative: Automated Demo Script

If manual recording is difficult, create a bash script that runs all commands automatically:

```bash
#!/bin/bash
# helep-demo.sh - Automated demo script

echo "Starting HELEP Demo..."
echo "======================"

# Start services
docker compose -f docker-compose.dev.yml up -d --build
sleep 30

# User registration
echo "1. User Registration"
TOKEN=$(curl -s -X POST localhost:8001/signup \
  -H 'content-type: application/json' \
  -d '{"phone":"+237600000001","password":"hunter22","role":"citizen"}' | jq -r '.token')

echo "Token: $TOKEN"

# SOS trigger
echo "2. SOS Trigger"
INCIDENT=$(curl -s -X POST localhost:8002/sos \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"lat":37.7749,"lon":-122.4194,"mode":"online"}')

echo "Incident: $INCIDENT"

# Wait for saga completion
sleep 5

# Check analytics
echo "3. Analytics"
curl -s localhost:8005/stats/events | jq .

echo "Demo complete!"
```

This script can be recorded or used for automated testing.