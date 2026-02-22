# Architecture

## Overview

```
                    ┌─────────────────────────────────────────┐
                    │            GitHub Actions                │
                    │   Lint → Test → Build → Push → Deploy   │
                    └──────────────┬──────────────────────────┘
                                   │ SSH + Ansible
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  AWS EC2 (t2.micro, Ubuntu 24.04)                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Docker Compose                                        │ │
│  │  ┌──────────────────┐     ┌──────────────────────┐     │ │
│  │  │  FastAPI App      │────▶│  PostgreSQL 16       │     │ │
│  │  │  (port 8000)      │     │  (internal only)     │     │ │
│  │  │  - Rate limiting  │     │  - Encrypted volume  │     │ │
│  │  │  - JSON logging   │     │  - Persistent data   │     │ │
│  │  │  - API key auth   │     └──────────────────────┘     │ │
│  │  └──────────────────┘                                   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────┐     ┌──────────────────────┐        │
│  │  CloudWatch Agent  │────▶│  AWS CloudWatch      │        │
│  │  (log forwarder)   │     │  - Log groups        │        │
│  └────────────────────┘     │  - Metric filters    │        │
│  ┌────────────────────┐     │  - Alarms → SNS      │        │
│  │  Fail2ban + UFW    │     └──────────────────────┘        │
│  └────────────────────┘                                     │
│  Security Group: SSH (admin IP only), 8000 (public)         │
└─────────────────────────────────────────────────────────────┘
```

## Design Decisions

### Why FastAPI over Flask?

FastAPI provides automatic OpenAPI documentation, built-in request validation via Pydantic, and modern Python type hints. For an API-only project, it's a better fit than Flask and demonstrates familiarity with current Python web frameworks.

### Why PostgreSQL over SQLite?

SQLite would be simpler (single file, no extra container), but PostgreSQL demonstrates a production-realistic setup. It also runs inside the Docker network with no port exposed to the host, which is a security best practice to highlight.

### Why EC2 over ECS/Fargate?

Simplicity. For a single-service demo, EC2 + Docker Compose is easier to understand, debug, and costs less. ECS would be the right choice for multi-service production workloads.

### Why GHCR over ECR?

GitHub Container Registry keeps the entire workflow in GitHub (code, CI/CD, images), is free for public repos, and requires no additional AWS configuration. ECR would add complexity for no benefit at this scale.

### Why local Terraform state?

For a single-developer demo project, local state avoids the bootstrapping complexity of creating S3 + DynamoDB before running Terraform. The README documents how to migrate to S3 backend for team use.

### Why Ansible for config management?

Ansible is required by the project spec and is a natural fit for "Day 2" operations — installing Docker, hardening the OS, configuring fail2ban, deploying the app. Terraform creates the infrastructure; Ansible configures it.

## Monitoring Architecture

```
App Container (JSON logs)
        │
        ▼
Docker json-file log driver
        │
        ▼
CloudWatch Agent (reads /var/lib/docker/containers/*-json.log)
        │
        ▼
CloudWatch Logs (/app/chuck-norris-api)
        │
        ├──▶ Metric Filter: auth_failure     ──▶ Alarm (>20 in 5min) ──▶ SNS Email
        ├──▶ Metric Filter: brute_force      ──▶ Alarm (any)          ──▶ SNS Email
        ├──▶ Metric Filter: server_error     ──▶ Alarm (>10 in 5min)  ──▶ SNS Email
        │
        ├──▶ EC2 StatusCheckFailed           ──▶ Alarm (2 consecutive) ──▶ SNS Email
        └──▶ EC2 CPUUtilization              ──▶ Alarm (>80% for 15m)  ──▶ SNS Email
```

### Log Format

Every HTTP request generates a JSON log entry:

```json
{
  "timestamp": "2026-02-18T14:30:00.000Z",
  "level": "INFO",
  "logger": "chuck_norris_api",
  "message": "Request completed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "GET",
  "path": "/jokes/random",
  "status_code": 200,
  "client_ip": "203.0.113.45",
  "user_agent": "curl/7.88.1",
  "response_time_ms": 12.5,
  "event_type": "http_request"
}
```

### Security Event Types

| event_type | Level | Trigger |
|-----------|-------|---------|
| `http_request` | INFO | Normal request |
| `auth_failure` | WARNING | 401/403 response |
| `server_error` | ERROR | 5xx response |
| `brute_force_detected` | CRITICAL | >10 auth failures from same IP in 5min |
| `spray_attack_detected` | CRITICAL | >20 total auth failures in 5min |
| `joke_created` | INFO | New joke added |
| `api_key_created` | INFO | New API key generated |

## Scaling Considerations

This architecture is designed for a demo/interview. For production scaling:

- **Horizontal scaling:** Move to ECS Fargate with an Application Load Balancer
- **Database:** Migrate to RDS PostgreSQL with Multi-AZ for high availability
- **Caching:** Add Redis for rate limiting state and frequently accessed jokes
- **CDN:** Put CloudFront in front for global distribution
- **TLS:** Add ACM certificate with ALB or use Caddy as reverse proxy on EC2
