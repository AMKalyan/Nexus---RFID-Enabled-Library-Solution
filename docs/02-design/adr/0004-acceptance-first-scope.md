# ADR-0004: Acceptance-scenario-first delivery scope

- Status: Accepted
- Date: 2026-10-04

## Context
The full scope (12 functional requirements, 9 non-functional requirements, 9 deliverables) is larger than a 48-hour build allows (R-01). The ten priority acceptance scenarios (SOP §8) define what must be demonstrable.

## Decision
- Build every acceptance scenario end-to-end, through UI, API, middleware and data, with an automated acceptance test.
- Implement the remaining functional items as thin but working features where cheap: spine-label PDF, patron-card PDF, virtual bookshelf, net-cataloguing import.
- Record acquisition and serials as **Partial**, with minimal data structures and documented extensions.
- Track every requirement's true status in the RTM, and list the remaining work in the production-completion backlog.

## Consequences
- The demonstration covers all graded scenarios reliably.
- Some FR 01 sub-features are intentionally shallow, and are documented as such rather than hidden.
