# API Reference

Base URL: `http://<server-ip>:8000`

Interactive documentation: `http://<server-ip>:8000/docs`

---

## Authentication

Write endpoints require an API key passed in the `X-API-Key` header.
The API key generation endpoint requires the admin secret (set in `.env`).

API keys are hashed with SHA-256 before storage — the raw key is shown only once at creation time.

---

## Endpoints

### General

#### `GET /`

Welcome message with endpoint overview.

**Response:** `200 OK`

```json
{
  "message": "Welcome to the Chuck Norris Jokes API!",
  "docs": "/docs",
  "endpoints": { ... }
}
```

#### `GET /health`

Health check for monitoring. Returns database connectivity status.

**Response:** `200 OK`

```json
{
  "status": "ok",
  "database": "healthy",
  "timestamp": "2026-02-18T12:00:00Z"
}
```

---

### Jokes

#### `GET /jokes/random`

Returns a random joke.

**Response:** `200 OK`

```json
{
  "id": 7,
  "text": "Chuck Norris can slam a revolving door.",
  "created_at": "2026-02-18T12:00:00Z"
}
```

**Error:** `404` if no jokes exist.

#### `GET /jokes/{id}`

Returns a specific joke by ID.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | int (path) | Joke ID |

**Response:** `200 OK` — same format as above.

**Error:** `404` if joke not found.

#### `GET /jokes`

Paginated list of all jokes.

**Query Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `page` | int | 1 | Page number (>= 1) |
| `per_page` | int | 10 | Items per page (1–100) |

**Response:** `200 OK`

```json
{
  "jokes": [ ... ],
  "total": 20,
  "page": 1,
  "per_page": 10
}
```

#### `POST /jokes`

Add a new joke. **Requires API key.**

**Headers:** `X-API-Key: cnj_your_key_here`

**Body:**

```json
{
  "text": "Chuck Norris can compile syntax errors."
}
```

**Validation:**

- `text` must be 10–500 characters
- Whitespace-only strings are rejected
- Duplicate jokes return `409 Conflict`

**Response:** `201 Created`

---

### Authentication

#### `POST /api-keys`

Generate a new API key. **Requires admin secret.**

**Headers:** `X-API-Key: YOUR_ADMIN_SECRET`

**Body:**

```json
{
  "name": "my-app"
}
```

**Response:** `201 Created`

```json
{
  "name": "my-app",
  "api_key": "cnj_abc123...",
  "message": "Store this key securely — it will not be shown again."
}
```

---

## Rate Limits

| Endpoint Type | Limit |
|---------------|-------|
| Read (`GET`) | 60 requests/minute per IP |
| Write (`POST /jokes`) | 10 requests/minute per IP |
| Key generation | 5 requests/minute per IP |

Exceeding the limit returns `429 Too Many Requests`.

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Human-readable error message."
}
```

| Code | Meaning |
|------|---------|
| `401` | Missing API key |
| `403` | Invalid or deactivated API key |
| `404` | Resource not found |
| `409` | Duplicate joke |
| `422` | Validation error (bad input) |
| `429` | Rate limit exceeded |
| `500` | Server error |

---

## Request Tracing

Every response includes an `X-Request-ID` header. Use this value when reporting issues or correlating logs.
