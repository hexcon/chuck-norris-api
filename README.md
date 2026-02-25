# Chuck Norris Jokes API

A REST API for Chuck Norris jokes, built with FastAPI and PostgreSQL. Deployed to AWS EC2 using Terraform, Ansible, and GitHub Actions.

## Overview

The API serves jokes through public read endpoints and requires API key authentication for writes. Infrastructure is fully codified — Terraform provisions AWS resources, Ansible handles server configuration and hardening, and GitHub Actions runs the CI/CD pipeline.

**Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · Docker · Terraform · Ansible · GitHub Actions · AWS (EC2, CloudWatch, SNS)

## Local Development

Requires Docker and Docker Compose.

```bash
git clone https://github.com/hexcon/chuck-norris-api.git
cd chuck-norris-api
cp .env.example .env    # set a strong ADMIN_SECRET
docker compose up -d
```

The API runs at `http://localhost:8000`. Swagger docs at `/docs`, ReDoc at `/redoc`.

### Running Tests

```bash
pip install -r requirements.txt
DATABASE_URL=sqlite:///./test.db ADMIN_SECRET=test pytest tests/ -v
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | — | Health check (includes DB status) |
| `GET` | `/jokes/random` | — | Random joke |
| `GET` | `/jokes/{id}` | — | Joke by ID |
| `GET` | `/jokes?page=1&per_page=10` | — | Paginated listing |
| `POST` | `/jokes` | API Key | Add a joke |
| `POST` | `/api-keys` | Admin | Generate an API key |

### Generating an API Key

```bash
curl -X POST http://localhost:8000/api-keys \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_ADMIN_SECRET" \
  -d '{"name": "my-key"}'
```

The key is returned once and not stored in plaintext — save it.

## Infrastructure

### Architecture

```
GitHub Actions (CI/CD)
  │
  ├── Lint (ruff) → Test (pytest) → Build & Push (GHCR) → Deploy (Ansible over SSH)
  │
  ▼
AWS EC2 (Ubuntu 24.04)
  ├── Docker
  │   ├── FastAPI app (non-root, read-only fs, resource-limited)
  │   └── PostgreSQL 16 (internal network only)
  ├── CloudWatch Agent → CloudWatch Logs → Metric Filters → Alarms → SNS (email)
  ├── UFW Firewall (deny all inbound except 22, 8000)
  └── Fail2ban (SSH brute force protection)
```

Terraform provisions the EC2 instance, security group, IAM role, CloudWatch log groups, metric filters, and alarms. Ansible configures the OS — installs Docker, hardens SSH, sets up fail2ban and UFW, deploys the CloudWatch agent, and runs the application containers.

### Provisioning

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Set: allowed_ssh_cidr, key_pair_name, alert_email
terraform init && terraform apply
```

### Server Configuration & Deploy

```bash
cd ansible
# Build inventory from Terraform output, then:
ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i inventory playbook.yml
```

See the [deployment guide](docs/architecture.md) for full step-by-step instructions.

### Teardown

```bash
cd terraform && terraform destroy
```

## CI/CD Pipeline

Triggered on push to `main`. Four stages:

1. **Lint** — ruff check and format verification
2. **Test** — pytest against SQLite (no external deps)
3. **Build** — multi-stage Docker build, push to GitHub Container Registry
4. **Deploy** — Ansible playbook over SSH to EC2, with dynamic security group rules for the runner's IP

Deploy requires GitHub environment approval (`production`).

### GitHub Secrets

| Secret | Value |
|--------|-------|
| `EC2_HOST` | EC2 public IP |
| `EC2_SSH_KEY` | SSH private key |
| `ADMIN_SECRET` | Admin secret for API key generation |
| `DB_PASSWORD` | PostgreSQL password |

`GITHUB_TOKEN` is provided automatically for GHCR authentication.

## Security

### Application Layer

- **Authentication:** API keys hashed with SHA-256, verified with constant-time comparison. Admin operations require a separate secret.
- **Rate limiting:** 60 req/min (reads), 10 req/min (writes), 5 req/min (key generation). Per-client IP.
- **Input validation:** Pydantic schemas with length constraints on all inputs.
- **SQL injection:** Mitigated by SQLAlchemy ORM — all queries are parameterized.
- **Brute force detection:** Middleware tracks auth failures per IP over a sliding 5-minute window. Fires alerts at 10 failures/IP or 20 failures globally (credential spray).

### Container Security

- Non-root user (`appuser`, no login shell)
- Read-only filesystem with tmpfs for `/tmp`
- `no-new-privileges` security option
- Resource limits: 0.5 CPU, 256MB memory
- PostgreSQL bound to internal Docker network only

### Host Security

- SSH hardened: key-only auth, root login disabled, max 3 auth attempts, no TCP/X11 forwarding
- Fail2ban on SSH (1-hour ban after 5 failures)
- UFW firewall: deny-all inbound, allow 22 and 8000
- IMDSv2 enforced on EC2 (blocks SSRF to instance metadata)
- Encrypted EBS volume
- Automatic security updates via `unattended-upgrades`

Full OWASP Top 10 review and hardening checklist: [docs/security.md](docs/security.md)

## Monitoring

Every request is logged as structured JSON with a unique request ID, client IP, response time, and status code. Logs are forwarded to CloudWatch via the CloudWatch Agent.

CloudWatch alarms notify via SNS email on:

- EC2 instance health check failure
- Auth failure spike (>20 in 5 min)
- Brute force detection event
- Server error spike (>10 in 5 min)
- Sustained high CPU (>80% for 15 min)

Architecture details: [docs/architecture.md](docs/architecture.md)

## Project Structure

```
├── app/                     # Application code
│   ├── main.py              # Routes and lifespan
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── auth.py              # API key auth
│   ├── middleware.py         # Logging, brute force detection
│   ├── database.py          # DB engine and sessions
│   ├── logging_config.py    # JSON log formatter
│   └── seed_data.py         # Initial joke data
├── tests/                   # pytest suite
├── terraform/               # AWS infrastructure
├── ansible/                 # Server config and deployment
├── .github/workflows/       # CI/CD pipeline
├── docs/                    # Architecture, security, API docs
├── Dockerfile               # Multi-stage build
├── docker-compose.yml       # Local dev
└── docker-compose.prod.yml  # Production overlay
```

## License

MIT
