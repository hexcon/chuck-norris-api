# 🤠 Chuck Norris Jokes API

A RESTful API serving Chuck Norris jokes, built with FastAPI and PostgreSQL, deployed to AWS EC2 with full CI/CD automation.

**Tech Stack:** FastAPI · PostgreSQL · Docker · Terraform · Ansible · GitHub Actions · AWS (EC2, CloudWatch)

---

## Table of Contents

- [Quick Start (Local)](#quick-start-local)
- [API Usage](#api-usage)
- [AWS Deployment Guide](#aws-deployment-guide)
- [CI/CD Pipeline](#cicd-pipeline)
- [Project Structure](#project-structure)
- [Security](#security)
- [Monitoring](#monitoring)
- [Documentation](#documentation)

---

## Quick Start (Local)

### Prerequisites

- Docker and Docker Compose
- Git

### Run locally

```bash
# Clone the repository
git clone https://github.com/YOUR_USER/chuck-norris-api.git
cd chuck-norris-api

# Create environment file
cp .env.example .env
# Edit .env and set a strong ADMIN_SECRET

# Start the application
docker compose up -d

# Verify it's running
curl http://localhost:8000/health
```

The API is now running at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Generate an API key (required for adding jokes)

```bash
# Use your ADMIN_SECRET from .env
curl -X POST http://localhost:8000/api-keys \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_ADMIN_SECRET" \
  -d '{"name": "my-first-key"}'
```

Save the returned `api_key` — it won't be shown again.

### Run tests

```bash
pip install -r requirements.txt
DATABASE_URL=sqlite:///./test.db ADMIN_SECRET=test pytest tests/ -v
```

---

## API Usage

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | None | Welcome message |
| `GET` | `/health` | None | Health check |
| `GET` | `/jokes/random` | None | Random joke |
| `GET` | `/jokes/{id}` | None | Joke by ID |
| `GET` | `/jokes?page=1&per_page=10` | None | Paginated list |
| `POST` | `/jokes` | API Key | Add a joke |
| `POST` | `/api-keys` | Admin Secret | Generate API key |

### Examples

```bash
# Get a random joke
curl http://localhost:8000/jokes/random

# Get joke #5
curl http://localhost:8000/jokes/5

# Add a new joke
curl -X POST http://localhost:8000/jokes \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cnj_your_key_here" \
  -d '{"text": "Chuck Norris can compile syntax errors."}'
```

Full interactive documentation is available at `/docs` (Swagger UI) and `/redoc`.

---

## AWS Deployment Guide

This guide assumes a brand-new AWS account and no prior AWS experience.

### Step 1: AWS Account Setup

1. Create an AWS account at https://aws.amazon.com
2. **Enable MFA** on the root account (Security best practice)
3. Create an IAM user for Terraform:
   - Go to IAM → Users → Create User
   - Name: `terraform-admin`
   - Attach policy: `AdministratorAccess` (for demo; use scoped policies in production)
   - Create access keys → Download the CSV

4. Install the AWS CLI:
   ```bash
   # macOS
   brew install awscli

   # Linux
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip && sudo ./aws/install
   ```

5. Configure credentials:
   ```bash
   aws configure
   # Enter your Access Key ID, Secret Access Key, region: eu-north-1, output: json
   ```

### Step 2: Create an SSH Key Pair

```bash
# Create a key pair in AWS
aws ec2 create-key-pair \
  --key-name chuck-norris-key \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/chuck-norris-key.pem

chmod 600 ~/.ssh/chuck-norris-key.pem
```

### Step 3: Terraform — Provision Infrastructure

```bash
# Install Terraform: https://developer.hashicorp.com/terraform/install
cd terraform

# Create your variables file
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars:
#   allowed_ssh_cidr = "YOUR_IP/32"  (run: curl -s ifconfig.me)
#   key_pair_name    = "chuck-norris-key"
#   alert_email      = "your@email.com"

# Initialize and apply
terraform init
terraform plan    # Review what will be created
terraform apply   # Type 'yes' to confirm

# Note the outputs — you'll need the IP address
terraform output
```

> **Important:** Check your email and confirm the SNS subscription for CloudWatch alerts.

### Step 4: Ansible — Configure Server and Deploy

```bash
# Install Ansible
pip install ansible

# Create inventory file
cd ../ansible
SERVER_IP=$(cd ../terraform && terraform output -raw instance_public_ip)

cat > inventory <<EOF
[app_servers]
${SERVER_IP} ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/chuck-norris-key.pem
[app_servers:vars]
ansible_python_interpreter=/usr/bin/python3
EOF

# Run the playbook (set required env vars)
export ADMIN_SECRET=$(openssl rand -base64 24)
export DB_PASSWORD=$(openssl rand -base64 24)
export GITHUB_REPO="your-user/chuck-norris-api"

echo "Save these secrets:"
echo "  ADMIN_SECRET: $ADMIN_SECRET"
echo "  DB_PASSWORD:  $DB_PASSWORD"

ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i inventory playbook.yml
```

### Step 5: Verify

```bash
curl http://${SERVER_IP}:8000/health
curl http://${SERVER_IP}:8000/jokes/random
```

### Teardown

```bash
cd terraform
terraform destroy  # Type 'yes' to confirm — removes all AWS resources
```

---

## CI/CD Pipeline

The GitHub Actions pipeline runs on every push to `main`:

```
┌──────┐    ┌──────┐    ┌───────────┐    ┌────────┐
│ Lint │───▶│ Test │───▶│ Build &   │───▶│ Deploy │
│      │    │      │    │ Push GHCR │    │ (SSH)  │
└──────┘    └──────┘    └───────────┘    └────────┘
```

### Required GitHub Secrets

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `EC2_HOST` | EC2 public IP from Terraform output |
| `EC2_SSH_KEY` | Contents of your `.pem` file |
| `ADMIN_SECRET` | Admin secret for API key generation |
| `DB_PASSWORD` | PostgreSQL password |

> `GITHUB_TOKEN` is automatically provided — no setup needed for GHCR.

---

## Project Structure

```
chuck-norris-api/
├── app/                    # Application source code
│   ├── main.py             # FastAPI routes
│   ├── models.py           # SQLAlchemy models
│   ├── database.py         # Database connection
│   ├── schemas.py          # Pydantic validation
│   ├── auth.py             # API key authentication
│   ├── middleware.py        # Logging & rate limiting
│   ├── logging_config.py   # Structured JSON logging
│   └── seed_data.py        # Pre-loaded jokes
├── tests/                  # Automated tests
├── terraform/              # Infrastructure as Code
├── ansible/                # Configuration management
├── .github/workflows/      # CI/CD pipeline
├── docs/                   # Additional documentation
├── Dockerfile              # Multi-stage, hardened
└── docker-compose.yml      # Local development
```

---

## Security

See [docs/security.md](docs/security.md) for the full OWASP Top 10 review and server hardening checklist.

Key security measures implemented:

- API key authentication (SHA-256 hashed, constant-time comparison)
- Rate limiting (60 req/min read, 10 req/min write)
- Non-root Docker containers with read-only filesystem
- SSH hardened (key-only, no root, max 3 retries)
- Fail2ban for brute force protection
- IMDSv2 enforced on EC2 (SSRF mitigation)
- Input validation on all endpoints
- PostgreSQL not exposed to internet
- Encrypted EBS volume
- Automated security updates

---

## Monitoring

See [docs/architecture.md](docs/architecture.md) for the monitoring architecture.

- **Health endpoint:** `GET /health` — returns database connectivity status
- **Structured JSON logs** — every request logged with request ID, client IP, response time
- **CloudWatch Alarms:** Instance health, auth failure spikes, brute force detection, server errors, high CPU
- **Alert notifications** via SNS email

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/api.md](docs/api.md) | API reference |
| [docs/architecture.md](docs/architecture.md) | Architecture decisions and diagrams |
| [docs/security.md](docs/security.md) | OWASP Top 10 review and hardening |
| [docs/siem-integration.md](docs/siem-integration.md) | SIEM forwarding guide |
| `/docs` endpoint | Auto-generated Swagger UI |

---

## Terraform State — S3 Backend Migration

This project uses local Terraform state for simplicity. To migrate to S3 for team collaboration:

```bash
# 1. Create S3 bucket and DynamoDB table for locking
aws s3api create-bucket \
  --bucket chuck-norris-tf-state \
  --region eu-north-1 \
  --create-bucket-configuration LocationConstraint=eu-north-1

aws s3api put-bucket-versioning \
  --bucket chuck-norris-tf-state \
  --versioning-configuration Status=Enabled

aws dynamodb create-table \
  --table-name chuck-norris-tf-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# 2. Add backend block to terraform/main.tf:
#    backend "s3" {
#      bucket         = "chuck-norris-tf-state"
#      key            = "terraform.tfstate"
#      region         = "eu-north-1"
#      dynamodb_table = "chuck-norris-tf-lock"
#      encrypt        = true
#    }

# 3. Run: terraform init -migrate-state
```

---

## License

MIT
