# Security Documentation

## OWASP Top 10 (2021) Review

| # | Category | Status | What We Did | Accepted Risk |
|---|----------|--------|-------------|---------------|
| A01 | **Broken Access Control** | ✅ Mitigated | Write endpoints require API key auth. Admin endpoint requires separate admin secret. Keys are hashed (SHA-256) and compared using constant-time comparison (`secrets.compare_digest`). | Read endpoints are intentionally public (jokes are not sensitive data). |
| A02 | **Cryptographic Failures** | ✅ Mitigated | API keys hashed with SHA-256 before storage — raw keys never stored. DB credentials passed via environment variables, not hardcoded. EBS volume encrypted at rest. | SHA-256 is sufficient for API keys (high entropy input). Bcrypt would be overkill here. |
| A03 | **Injection** | ✅ Mitigated | SQLAlchemy ORM prevents SQL injection — all queries are parameterized. Pydantic validates and sanitizes all input. FastAPI auto-validates path parameter types (e.g., `joke_id: int` rejects `1 OR 1=1`). | No raw SQL used anywhere in the codebase. |
| A04 | **Insecure Design** | ✅ Mitigated | Rate limiting on all endpoints (60/min read, 10/min write, 5/min key gen). Separation of admin secret from API keys. Brute force detection in middleware. | Single-service design appropriate for scope. |
| A05 | **Security Misconfiguration** | ✅ Mitigated | Docker runs as non-root user with read-only filesystem. IMDSv2 enforced on EC2 (blocks SSRF metadata attacks). SSH hardened (no root, no password, max 3 retries). UFW firewall as defense-in-depth. No debug mode in production. | No TLS — documented as next step. Port 8000 is publicly accessible. |
| A06 | **Vulnerable and Outdated Components** | ✅ Mitigated | All dependencies pinned to specific versions. Automated OS security updates via `unattended-upgrades`. GitHub Actions pipeline rebuilds image on every push. | Dependency scanning (Dependabot/Snyk) not configured — would add for production. |
| A07 | **Identification and Authentication Failures** | ✅ Mitigated | Cryptographically random API keys (`secrets.token_urlsafe`). Constant-time comparison prevents timing attacks. Rate limiting prevents brute force. Fail2ban protects SSH. | No API key rotation mechanism — would add for production. No key expiry. |
| A08 | **Software and Data Integrity Failures** | ✅ Mitigated | Docker image built in CI/CD with pinned base image. Multi-stage build reduces attack surface. Container runs with `no-new-privileges` and `read_only` in production. | Image signing (cosign/Notary) not implemented — would add for production. |
| A09 | **Security Logging and Monitoring Failures** | ✅ Mitigated | Every request logged with structured JSON (request ID, client IP, user agent, response time). Security events (auth failures, brute force) logged at WARNING/CRITICAL. CloudWatch alarms on failure spikes, brute force, and server errors. SNS email notifications. | Log integrity verification not implemented. SIEM integration documented but not built. |
| A10 | **Server-Side Request Forgery (SSRF)** | ✅ Mitigated | IMDSv2 enforced — EC2 metadata requires session token (blocks common SSRF vector). Application does not make outbound requests based on user input. No URL parameters accepted. | N/A — no user-controlled outbound requests exist. |

---

## Server Hardening Checklist

### OS Level

| Control | Implementation | File |
|---------|---------------|------|
| ✅ Automated security updates | `unattended-upgrades` configured | `ansible/playbook.yml` |
| ✅ SSH: Key-only authentication | `PasswordAuthentication no` | `ansible/playbook.yml` |
| ✅ SSH: Root login disabled | `PermitRootLogin no` | `ansible/playbook.yml` |
| ✅ SSH: Max 3 auth retries | `MaxAuthTries 3` | `ansible/playbook.yml` |
| ✅ SSH: No X11 forwarding | `X11Forwarding no` | `ansible/playbook.yml` |
| ✅ SSH: No TCP forwarding | `AllowTcpForwarding no` | `ansible/playbook.yml` |
| ✅ Fail2ban for SSH protection | 5 retries, 1h ban, 10min window | `ansible/playbook.yml` |

### Network Level

| Control | Implementation | File |
|---------|---------------|------|
| ✅ Security Group: SSH restricted to admin IP | `allowed_ssh_cidr` variable | `terraform/main.tf` |
| ✅ Security Group: Only ports 22 + 8000 open | Minimal ingress rules | `terraform/main.tf` |
| ✅ UFW firewall (defense-in-depth) | Default deny incoming | `ansible/playbook.yml` |
| ✅ PostgreSQL not exposed to host | Internal Docker network only | `docker-compose.yml` |
| ✅ IMDSv2 enforced | `http_tokens = "required"` | `terraform/main.tf` |

### Docker Level

| Control | Implementation | File |
|---------|---------------|------|
| ✅ Non-root user | `USER appuser` in Dockerfile | `Dockerfile` |
| ✅ Read-only filesystem | `read_only: true` in prod compose | `docker-compose.prod.yml` |
| ✅ No new privileges | `no-new-privileges:true` | `docker-compose.prod.yml` |
| ✅ Resource limits | CPU 0.5, Memory 256M | `docker-compose.prod.yml` |
| ✅ Multi-stage build | Separate builder and runtime stages | `Dockerfile` |
| ✅ Minimal base image | `python:3.12-slim` | `Dockerfile` |
| ✅ App code read-only | `chmod 555` on /app | `Dockerfile` |
| ✅ Health check | Built-in `HEALTHCHECK` directive | `Dockerfile` |
| ✅ Log rotation | `max-size: 10m`, `max-file: 5` | `docker-compose.prod.yml` |

### Application Level

| Control | Implementation | File |
|---------|---------------|------|
| ✅ Input validation | Pydantic schemas with constraints | `app/schemas.py` |
| ✅ API key hashing | SHA-256, never stored raw | `app/auth.py` |
| ✅ Constant-time comparison | `secrets.compare_digest` for admin | `app/auth.py` |
| ✅ Rate limiting | slowapi per-IP limits | `app/main.py` |
| ✅ Request tracing | UUID per request in `X-Request-ID` | `app/middleware.py` |
| ✅ Brute force detection | In-app tracking + alerting | `app/middleware.py` |
| ✅ No secrets in code | `.env` file, git-ignored | `.gitignore` |
| ✅ Dependency pinning | Exact versions in requirements.txt | `requirements.txt` |

### CI/CD Level

| Control | Implementation | File |
|---------|---------------|------|
| ✅ Secrets in GitHub Secrets | Not in code or env files | `.github/workflows/ci-cd.yml` |
| ✅ Minimal permissions | `contents: read, packages: write` | `.github/workflows/ci-cd.yml` |
| ✅ Linting in pipeline | `ruff check` before merge | `.github/workflows/ci-cd.yml` |
| ✅ Tests before deploy | `pytest` must pass | `.github/workflows/ci-cd.yml` |
| ✅ Production environment gate | Requires `production` env approval | `.github/workflows/ci-cd.yml` |

---

## Known Limitations and Future Improvements

These are intentionally not implemented to keep the demo scope manageable, but would be required for production:

| Improvement | Priority | Notes |
|-------------|----------|-------|
| TLS/HTTPS | High | Use Caddy reverse proxy or ALB + ACM certificate |
| API key rotation | High | Add expiry dates and rotation endpoint |
| Dependency scanning | High | Enable Dependabot or Snyk in CI |
| Image signing | Medium | Sign images with cosign in CI/CD |
| WAF | Medium | AWS WAF on ALB for OWASP rule sets |
| VPC isolation | Medium | Place EC2 in private subnet with NAT gateway |
| Secrets manager | Medium | Use AWS Secrets Manager instead of .env |
| Database backups | Medium | Automated pg_dump or switch to RDS with snapshots |
| Log integrity | Low | CloudWatch Logs with tamper-proof configuration |
| Penetration testing | Low | Run OWASP ZAP or similar against the API |
