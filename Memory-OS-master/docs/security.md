# Security

- Passwords hashed; never stored in plaintext.
- API keys: raw secret shown once at creation; only a peppered HMAC-SHA256 hash
  stored (`security/keys.py`). Verified with constant-time comparison.
- JWT users need `developer+` for memory writes; `viewer` cannot mutate (`require_memory_write`).
- Webhook URLs validated against SSRF (private IPs, localhost blocked).
- Webhook signing secrets encrypted at rest (`secret_enc`); deliveries signed correctly.
- Auth login/register rate limited (20/min per IP).
- API keys looked up by full key hash, not prefix alone.
- Anonymous access disabled by default (`MEMORY_OS_ALLOW_ANON=false`); enable only for local dev.
- Production startup fails on weak `JWT_SECRET` / `API_KEY_PEPPER`, anon mode, or missing `METRICS_TOKEN`.
- `/metrics` requires `METRICS_TOKEN` (Bearer or `X-Metrics-Token`) when configured; always required in production.
- Consistent error envelope; stack traces never exposed to clients.
- Secure headers (nosniff, frame-deny, referrer) on every response.
- Request IDs propagated via `X-Request-ID`.
- Never logged: passwords, raw API keys, tokens, secrets.
