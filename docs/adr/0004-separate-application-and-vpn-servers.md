# ADR 0004: Separate Application And VPN Servers

- Status: Accepted
- Date: 2026-06-13

## Context

AGentVPN handles identities, payments, subscriptions, Telegram integration, and
provisioning orchestration. The existing Germany server handles user VPN traffic through
3x-ui, Xray, and Hysteria2.

Combining both workloads would make application maintenance, database incidents, and VPN
traffic compete for the same resources and create a larger single point of failure.

## Decision

Use two separate production servers:

1. AGentVPN application server: 2 vCPU, 4 GB RAM, 1 Gbit/s network port.
2. Germany VPN server: 2 vCPU, 4 GB RAM, 1 Gbit/s network port with unlimited traffic.

The AGentVPN server communicates with 3x-ui over HTTPS. Firewall rules on the VPN server
allow management API access only from the fixed public IP of the AGentVPN server.

## Consequences

- VPN traffic does not consume application server resources.
- Application deployments do not interrupt existing VPN connections.
- PostgreSQL and Redis remain private to the application server.
- A secure network path and firewall allowlist between the servers are mandatory.
- Both servers require independent monitoring and external backups.

