# ADR 0005 — Authentication: Argon2id, short access JWT, rotating refresh cookie

Status: Accepted

## Context

Requirement: secure authentication, RBAC, protection against unauthenticated access and
privilege escalation. The UI is a browser SPA served same-origin; the API is also
scriptable. Tokens in `localStorage` are readable by any XSS, so the long-lived
credential must not live there.

## Decision

**Passwords.** Argon2id (`argon2-cffi` defaults = RFC 9106 low-memory profile),
salted, PHC-encoded, transparently re-hashed at login when parameters are raised.
Length-based policy (NIST SP 800-63B): 12–128 characters, no control characters,
not trivially repetitive, not the e-mail or its local part. No composition rules.

**Access token.** JWT, **HS256 pinned** (`alg=none`, HS384/512 and key-confusion are
rejected), 15 minutes. Mandatory claims `exp iat iss aud sub jti`. A distinct audience
per token type means a refresh token is never accepted as an access token and vice
versa. The access token is held in JS memory only.

**Refresh token.** JWT carried **only** in an `HttpOnly; SameSite=Strict; Path=/api/v1/auth`
cookie (`Secure` when `NEO_COOKIE_SECURE=true`, mandatory in production), 7 days. Each use
**rotates** it. Every token belongs to a *family* recorded server-side
(`refresh_tokens`). Presenting an already-rotated token while its family is still alive
is treated as theft: the **whole family is revoked** and an
`auth.refresh_reuse_detected` audit event is written. Presenting a token of an
already-dead family (after logout, deactivation or a previous alert) is just refused,
without a new alert.

**CSRF.** Cookie-authenticated endpoints (`/auth/refresh`, `/auth/logout`) additionally
require the header `X-Neo-CSRF: 1`; cross-site forms cannot set custom headers and CORS
is closed by default.

**Per-request revalidation.** Role, activity and organisation are re-read from the
database on every request, so deactivation and demotion take effect immediately rather
than when the token expires. A token whose `org` claim contradicts the database is
rejected.

**Brute force.** Per-account lockout (5 failures → 15 minutes, configurable). Unknown
accounts, wrong passwords, locked and inactive accounts return the **same** response, and
unknown accounts still cost one hash verification (no user enumeration by content or
timing). Every outcome is audited with the real reason.

**Bootstrap.** Organisations and their first admin are created only by the CLI
(`neo-orchestro create-org`); the password comes from stdin or an interactive prompt,
never argv.

## Alternatives rejected

- *Opaque server sessions only* — simpler revocation, but couples every API call to a
  session store; the access JWT + server-side refresh family gives both.
- *RS256/EdDSA* — useful when other services verify tokens; here only the API verifies,
  so a single HMAC secret is sufficient. Revisit when splitting services.
- *Access token in a cookie* — would need CSRF protection on every state-changing call.
- *Open self-registration* — wrong default for a security platform.

## Known limits (open)

- **Account lockout can be abused** to lock out a known e-mail (a deliberate trade-off).
  There is no per-IP rate limiting in the app: put the API behind a reverse proxy/WAF
  that limits `/api/v1/auth/*`.
- No absolute maximum session age (refresh is sliding, 7 days). No MFA/SSO yet.
- A single signing secret: rotation requires a restart and invalidates sessions (a key id
  and overlap window are a future improvement).
- The client IP is `request.client.host`; behind a proxy run uvicorn with
  `--proxy-headers --forwarded-allow-ips=<proxy>` so the audit trail records real IPs.
