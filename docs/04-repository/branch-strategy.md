# Branch Strategy and Repository Conventions

SOP reference: §10 Version control and Change control; deliverable D4.

## Branches

| Branch | Purpose | Lifetime |
|---|---|---|
| `main` | Always-releasable integration branch; only receives merges from closed stages or fixes | Permanent |
| `stage/N-<name>` | All work for SOP §9 Stage N (e.g. `stage/3-foundation`) | Until the Stage N gate is approved |
| `fix/<id>-<slug>` | Defect fix referenced in the defect log | Until the fix is merged and retested |

## Merge and review rules

1. Work happens on the stage branch, in small commits with conventional messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`, `ci:`).
2. At the end of a stage, the stage-gate record `docs/00-project-control/stage-gates/stage-N.md` is completed. It covers exit criteria, outputs, review notes, decisions and sign-off.
3. After sign-off, the branch is merged with `git merge --no-ff`, so every stage remains a visible unit in history. The merge commit is tagged `sop-stage-N`.
4. The next stage branch is cut from `main` only after the previous gate is merged. This enforces SOP §9: "Do not begin production-style integration until the preceding review is complete."
5. Hosted merge requests replace step 3 once the repository has a remote; the gate record stays the review evidence.

## Tags

| Tag | Meaning |
|---|---|
| `sop-stage-1` … `sop-stage-7` | Stage gate approved and merged |
| `v1.0.0` / `v1.0.1` | Release builds used for the offline install and update demonstration |
| `v1.0.0-eval` | Final evaluation release |

## Commit hygiene

- One logical change per commit; the message explains *why* when it isn't obvious.
- Requirement IDs (FR/NFR/AC) appear in commit bodies where relevant.
- Never commit secrets, real personal data, generated spreadsheets, backups or build artefacts (see `.gitignore`).
- Line endings are normalised by `.gitattributes`; shell scripts are always LF.
