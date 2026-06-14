# Threat Model

## Protected Assets

- 3x-ui and Robokassa credentials
- Telegram bot token and validated user sessions
- Happ subscription tokens and VPN share URIs
- Payment and subscription integrity
- User identity and payment history
- Admin privileges and audit history

## Primary Threats And Controls

| Threat | Impact | Initial controls |
|---|---|---|
| Forged Telegram initData | Account takeover | Server-side HMAC validation, `auth_date` limit, replay cache |
| Forged or replayed Robokassa ResultURL | Free or duplicate access | Password #2 signature validation, constant-time compare, event uniqueness, payment row lock, amount/order checks |
| Frontend claims successful payment | Free access | Ignore frontend payment result; activate only from verified webhook |
| Duplicate provisioning | Multiple 3x-ui clients | Stable external IDs, verify-before-create, advisory locks, no blind create retries |
| Partial two-protocol provisioning | Broken subscription presented as active | `partial_failed`, background resync, verification of both bindings, manual review threshold |
| Subscription URL leakage | Unauthorized VPN access | 256-bit opaque tokens, hash-only storage, revocation, rotation, rate limits, access-log redaction |
| IDOR on subscriptions or payments | Cross-user data exposure | Ownership checks in service layer and API tests |
| SSRF through provider URLs | Internal network access | Operator-configured allowlisted base URLs, no user-controlled outbound URL, redirect restrictions |
| 3x-ui exposed publicly | Panel compromise | Firewall/private network, backend IP allowlist, HTTPS, no browser access |
| Secret leakage in logs | Infrastructure compromise | Structured logging with denylist redaction and sanitized provider errors |
| Admin account abuse | Mass access changes | Telegram-ID allowlist or dedicated identity provider, RBAC, step-up checks, audit log |
| Redis lock loss or race | Double processing | Database constraints and row/advisory locks remain correctness boundary |
| Malicious oversized webhook | Resource exhaustion | Reverse-proxy and application body limits |
| Stolen database backup | User and token compromise | Encrypted backups, restricted storage, token hashes, restore access audit |
| Dependency or image compromise | Remote code execution | Locked dependencies, image pinning, CI scanning, minimal runtime images |

## Abuse Cases

### Payment Replay

An attacker replays a valid success webhook. The backend finds the unique webhook event,
locks the payment, observes that activation was already applied, and returns success
without extending or provisioning again.

### Subscription Enumeration

An attacker requests sequential paths. Tokens contain at least 256 bits of randomness and
no identifiers. Responses use uniform not-found behavior and rate limiting.

### Binding Collision

An attacker changes their Telegram username to match another user. Usernames are never
used as identity; stable numeric Telegram IDs and internal subscription IDs form external
client identifiers.

### Compromised Frontend

Malicious frontend code cannot reach 3x-ui or Robokassa credentials. Sensitive decisions,
ownership checks, payment validation, token creation, and provisioning remain server-side.

## Residual Risks To Validate

- Exact 3x-ui authentication and API semantics depend on the installed OpenAPI schema.
- Robokassa signature algorithm in `.env` must match the merchant cabinet and be
  confirmed with the first test-mode ResultURL before production sales.
- Happ deep links and Provider ID behavior must be confirmed from official documentation.
- Telegram Mini App framing headers must be tested in Telegram clients before deployment.
