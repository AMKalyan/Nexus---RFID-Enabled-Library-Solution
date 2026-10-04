# Stage Gate 1: Initiation and Controls (D0)

| Field | Value |
|---|---|
| SOP reference | §9 Stage 1 |
| Branch | `stage/1-initiation` |
| Gate date | 2026-10-04 |
| Reviewer / approver | Moksh |
| Outcome | Pending sign-off |

## Exit criteria (SOP §9 Stage 1 bullets)

| # | SOP requirement | Output | Evidence | Met |
|---|---|---|---|---|
| 1 | Create the repository and issue tracker | Git repository with `main` and stage branches; issue tracker | `.git`, `docs/00-project-control/issue-tracker.md`, `docs/04-repository/branch-strategy.md` | ☑ |
| 2 | Read the assignment and build the first requirements traceability matrix | RTM v0.1 covering FR 01–12, NFR 01–09, AC 01–10, D1–D9 | `docs/01-requirements/rtm.md` | ☑ |
| 3 | Record assumptions, questions, risks, dependencies and excluded work | Assumptions A-01..A-14, clarifications Q-01..Q-08, risks R-01..R-10, dependencies DEP-01..07, exclusions | `docs/01-requirements/assumptions-and-clarifications.md`, `docs/01-requirements/risks-dependencies-exclusions.md` | ☑ |
| 4 | Confirm that all data and credentials are synthetic | Signed declaration plus the controls that enforce it | `docs/01-requirements/synthetic-data-declaration.md`, `.gitignore` | ☑ |

## Additional controls established
- Engineering standards covering SOP §10 and NFR 02: `docs/00-project-control/engineering-standards.md`
- Defect log template: `docs/00-project-control/defect-log.md`
- Progress log and resume checklist: `docs/00-project-control/progress-log.md`
- Line-ending normalisation: `.gitattributes`

## Review notes
- The scope is too large for 48 hours (R-01). Mitigation agreed: acceptance-scenario-first delivery, with honest Partial/Backlog statuses in the RTM.
- The SOP's deliverable and stage numbering overlap (Q-01, Q-02). The interpretation is recorded and applied consistently.
- The container runtime is still being installed (DEP-01). It does not block Stage 2, which is design only.

## Decision
☐ Approved: proceed to Stage 2 (Requirements and design)

Signed: ____________ (Moksh) Date: ____________
