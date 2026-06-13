# ADR 0001: Central Backend Is The Source Of Truth

- Status: Accepted
- Date: 2026-06-13

## Context

Payments, subscription periods, two-protocol provisioning, retries, and token revocation
must remain consistent even when external systems are unavailable or send duplicate events.

## Decision

PostgreSQL in the central backend owns all business state. 3x-ui is used only as a
provisioning engine. ENOT is queried and receives server-to-server requests, but verified
webhooks are processed into local payment state before business actions occur.

Mini App, bot, admin UI, and Happ clients communicate only with the central backend.

## Consequences

- External outages do not erase business intent or history.
- Reconciliation and retries are possible.
- Provisioning requires an explicit local state machine.
- The backend must protect strict ownership and idempotency boundaries.

