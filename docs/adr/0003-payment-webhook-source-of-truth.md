# ADR 0003: Verified Payment Webhook Triggers Activation

- Status: Accepted
- Date: 2026-06-13

## Context

Redirects, frontend status, query parameters, and screenshots are attacker-controlled and
cannot prove payment.

## Decision

Access activation starts only after an ENOT webhook passes signature, event, invoice,
order, amount, currency, and state-transition validation. Reconciliation can confirm
provider status but uses the same locked, idempotent activation service.

## Consequences

- Successful redirects display a checking state rather than granting access.
- Duplicate webhooks are harmless.
- Provider signature behavior must be verified before production.

