# SIEM Integration Guide

This application produces structured JSON logs designed for ingestion into any SIEM platform. This document covers integration paths for common SIEM solutions.

## Log Format

Every log entry is a single JSON object on one line:

```json
{
  "timestamp": "2026-02-18T14:30:00.000Z",
  "level": "WARNING",
  "logger": "chuck_norris_api",
  "message": "Authentication failure",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/jokes",
  "status_code": 403,
  "client_ip": "203.0.113.45",
  "user_agent": "python-requests/2.31.0",
  "response_time_ms": 3.2,
  "event_type": "auth_failure"
}
```

### Key Fields for SIEM Correlation

| Field | Use Case |
|-------|----------|
| `event_type` | Primary filter for detection rules |
| `client_ip` | Geo-IP enrichment, IP reputation lookup |
| `request_id` | Trace individual requests across logs |
| `api_key_id` | Track which key was used (present on authenticated requests) |
| `response_time_ms` | Anomaly detection (slow responses may indicate attack) |

---

## Integration: Microsoft Sentinel

Since the application logs are already in CloudWatch, there are two paths to Sentinel:

### Option A: AWS S3 → Sentinel (Recommended)

1. **Export CloudWatch Logs to S3:**
   - Create an S3 bucket for log export
   - Configure CloudWatch Logs subscription filter to stream to S3 via Kinesis Firehose
   - Set up lifecycle policy for log retention

2. **Connect Sentinel to S3:**
   - In Sentinel, install the **Amazon Web Services** data connector
   - Configure the S3 connector with your bucket ARN
   - Map the JSON fields to Sentinel's CommonSecurityLog schema

3. **Create Analytics Rules:**
   ```kql
   // Brute force detection
   CommonSecurityLog
   | where DeviceProduct == "chuck-norris-api"
   | where AdditionalExtensions contains "auth_failure"
   | summarize FailureCount = count() by SourceIP, bin(TimeGenerated, 5m)
   | where FailureCount > 10

   // Spray attack detection
   CommonSecurityLog
   | where DeviceProduct == "chuck-norris-api"
   | where AdditionalExtensions contains "auth_failure"
   | summarize FailureCount = count(), DistinctIPs = dcount(SourceIP) by bin(TimeGenerated, 5m)
   | where FailureCount > 20 and DistinctIPs > 5
   ```

### Option B: Lambda Forwarder (Real-time)

1. Create a Lambda function triggered by CloudWatch Logs subscription
2. Forward events to Sentinel's Log Analytics workspace via the HTTP Data Collector API
3. Lower latency than S3 path but higher operational complexity

---

## Integration: Splunk

### CloudWatch → Splunk

1. Install the **Splunk Add-on for AWS** on your Splunk instance
2. Configure a CloudWatch Logs input pointing to `/app/chuck-norris-api`
3. Set the sourcetype to `_json`

### Detection Searches

```spl
# Auth failure spike
index=aws sourcetype=_json event_type="auth_failure"
| timechart span=5m count by client_ip
| where count > 10

# Server error spike
index=aws sourcetype=_json event_type="server_error"
| timechart span=5m count
| where count > 10
```

---

## Integration: Elastic SIEM

1. Install Filebeat with the AWS module on the EC2 instance, or use CloudWatch Logs → S3 → Elastic Agent
2. Configure the JSON input to parse structured logs
3. Create detection rules in Elastic Security

---

## Custom SIEM / Syslog

For any SIEM that accepts syslog or HTTP ingestion:

1. Install `rsyslog` or `Fluent Bit` on the EC2 instance
2. Configure it to tail Docker JSON logs from `/var/lib/docker/containers/`
3. Forward to your SIEM's ingestion endpoint

### Fluent Bit example:

```ini
[INPUT]
    Name              tail
    Path              /var/lib/docker/containers/**/*-json.log
    Parser            docker
    Tag               app.*
    Refresh_Interval  5

[OUTPUT]
    Name              http
    Match             app.*
    Host              your-siem.example.com
    Port              8088
    URI               /services/collector/event
    Format            json
```

---

## Detection Rules to Implement

Regardless of which SIEM you use, implement these detection rules:

| Rule | Condition | Severity | Response |
|------|-----------|----------|----------|
| Brute force | >10 `auth_failure` from same IP in 5 min | High | Block IP, investigate |
| Credential spray | >20 `auth_failure` from >5 IPs in 5 min | High | Investigate, check for compromised keys |
| Error spike | >10 `server_error` in 5 min | Medium | Check application health |
| Slow response anomaly | `response_time_ms` > 2x baseline | Medium | Check for DoS or resource exhaustion |
| Off-hours activity | `api_key_created` outside business hours | Low | Verify legitimate admin action |
| New user agent | `user_agent` not seen in last 30 days | Info | Enrichment for investigations |
