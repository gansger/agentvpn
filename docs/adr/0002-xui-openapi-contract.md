# ADR 0002: Generate 3x-ui Integration From The Installed OpenAPI Contract

- Status: Accepted
- Date: 2026-06-13

## Context

3x-ui versions may differ in authentication, endpoints, payload fields, and timestamp
formats. Internet examples can be stale and unsafe for provisioning.

## Decision

Before implementing `ThreeXUIProvisioningProvider`, fetch
`{XUI_BASE_URL}/panel/api/openapi.json` from the installed panel and save the exact schema
as `docs/3x-ui-openapi.json`.

The typed client and contract tests will be based on this snapshot. A schema change must
be reviewed before the adapter is updated.

No 3x-ui request or response shape will be invented when the snapshot is unavailable.

## Consequences

- Initial integration is blocked until the owner configures safe panel access.
- Contract drift becomes visible in review and CI.
- Authentication fallback can be implemented only when supported by the installed version.

