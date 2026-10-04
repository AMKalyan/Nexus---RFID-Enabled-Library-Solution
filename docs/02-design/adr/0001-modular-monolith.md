# ADR-0001: Modular monolith with adapter boundaries

- Status: Accepted
- Date: 2026-10-04

## Context
The SOP requires seven distinct layers (§6) and a demonstrable separation between application logic, RFID middleware, interoperability and integrations. The build window is 48 hours for one developer, and the target site is a single isolated server.

## Decision
Build one FastAPI backend made of separate packages per layer (`services`, `middleware_rfid`, `interop`, `integrations`, `core`, `db`), plus a separately deployed `device-sim` process and a static React frontend. Cross-layer calls go only through explicit interfaces. Adapters are selected from configuration by a registry.

## Consequences
- One container to build, deploy, back up and roll back, which makes offline operation straightforward.
- Layer boundaries are visible in the code layout and enforced in review; an import-linter rule keeps the routers → services → db direction.
- Later scaling (for example a separate middleware service per site) needs the middleware package lifted into its own process. Its HTTP event contract already allows this.
