# Authentication, Sessions & RBAC

## Auth methods
Two bearer credentials are accepted on the API:

1. **JWT access token** — for dashboard users. Obtained from `/v1/auth/login` or
   `/v1/auth/register`. Self-contained HS256 (see `app/security/jwt.py`), carrying
   `sub`, `tenant_id`, and `role`. Default TTL 1 hour.
2. **API key** (`mos_<short>_<body>`) — for external agents and the SDKs. Peppered
   HMAC-SHA256 hash stored; the plaintext secret is shown exactly once.

For frictionless local exploration, when `MEMORY_OS_ALLOW_ANON=true` (default) and
no `Authorization` header is present, requests resolve to a demo tenant. Set it to
`false` to require authentication (as the test suite does).

## Refresh tokens & rotation
`/v1/auth/refresh` rotates the refresh token: the presented token is revoked and a
new one issued. If a **revoked** token is presented again (reuse), the entire token
family for that user is revoked — a standard detection for stolen refresh tokens.
Raw refresh tokens are never stored; only a peppered SHA-256 hash.

## RBAC
Roles form a strict hierarchy: `owner > admin > developer > analyst > viewer`.

- `require_role(Role.admin)` guards privileged routes (e.g. creating API keys or
  webhooks).
- `require_scope("memory:write")` checks API-key scopes; the `admin` scope implies
  all scopes.
- API keys with the `admin` scope are treated as `admin` for `require_role` checks
  (audit log, reflection, webhooks, etc.).

The first user registered in an organization becomes its `owner`.
