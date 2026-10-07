# Performance Results

These are observations on the development host, not certified figures (Q-08). The targets are the prototype goals recorded in the clarification log.

## Setup

| Item | Value |
|---|---|
| Date | 2026-10-07 |
| Host | Intel Core i5-1240P (12 cores, 16 threads), 16 GB RAM, Windows 11. Docker Desktop (WSL 2) with 16 CPUs and 7.6 GB available to containers |
| Stack | `docker compose` with the dev override: nginx (TLS) → API (one uvicorn process, uvloop and httptools) → PostgreSQL 16.4 |
| Data | 21,200 bibs, 21,577 items (seed plus the 20,000-row migration batch), 300 members |
| Tool | `backend/tests/perf/perf_async.py` (httpx and asyncio), run on the same host |
| Mix per iteration | 70% OPAC search (random term, 20 per page); 20% check-out and check-in pair on a 200-item pool, with each virtual user owning its own items; 10% dashboard |
| Command | `NEXUS_PASSWORD=… python tests/perf/perf_async.py --ca ../ops/nginx/certs/nexus.crt --users 50 --duration 60 --out …` |

## Results

| Run | Users | Requests | Errors | req/s | Search p50 / p95 / p99 (ms) | Check-out p50 / p95 / p99 (ms) | Check-in p95 (ms) | Dashboard p95 (ms) |
|---|---|---|---|---|---|---|---|---|
| [Below saturation](evidence/perf-10u-60s.json) | 10 | 5,435 | 0 | 90.4 | 61 / 82 / 118 | 187 / 227 / 264 | 203 | 230 |
| [Target load, before DEF-007](evidence/perf-50u-60s-before-def007.json) | 50 | 5,279 | 0 | 87.0 | 486 / 841 / 1,133 | 695 / 1,027 / 1,153 | 1,004 | 1,035 |
| [Target load, after DEF-007](evidence/perf-50u-60s.json) | 50 | 5,208 | 0 | 86.0 | 491 / 842 / 1,138 | 713 / 1,104 / 1,371 | 1,027 | 1,094 |
| [Diagnostic: 4 API workers (not a supported configuration)](evidence/perf-50u-30s-4-workers-diagnostic.json) | 50 | 4,909 (30 s) | 0 | 162.1 | 160 / 400 / 804 | 447 / 857 / 1,052 | 729 | 843 |

## Against the Q-08 targets

| Target | Measured | Outcome |
|---|---|---|
| 20k-row migration under 5 minutes | 13.7 s end to end, including the pre-commit backup ([migration run report](../05-data-migration/migration-run-report.md)) | Met |
| Search p95 under 500 ms at 50 concurrent users | 842 ms (82 ms at 10 users) | Not met at 50 users (DEF-008) |
| Check-out p95 under 300 ms at 50 concurrent users | 1,104 ms (227 ms at 10 users) | Not met at 50 users (DEF-008) |
| No errors under load | 0 errors in every run | Met |

## Analysis

1. **Throughput is flat at about 86–90 req/s from 10 to 50 users.** The extra latency at 50 users is queueing.
2. **The API process is the bottleneck.** Under load:
   - The API container ran at about 115% CPU, which is one saturated Python process.
   - PostgreSQL ran at 48–64% CPU.
   - Most database connections were "idle in transaction", meaning the database was waiting for the application.
   - The load generator used about 65% of one core, so it was not the limit.
3. **Profiling shows no single expensive code path.** Run in-process, a search takes about 16 ms and a circulation call about 20 ms, mostly in database round trips. The rest of the cost is the per-request overhead of synchronous endpoints in one process: several thread-pool hops per request, with 40 threads sharing one interpreter lock.
4. **More processes confirm it.** Running four API workers as a diagnostic nearly doubled throughput (162 req/s) and brought search p95 to 400 ms, inside the target. Four workers is not a supported configuration yet, because the device command bus, the live hub, smart-card challenges, rate-limit counters and the outbox worker all hold state inside one process. See DEF-008 and the production backlog.
5. **One query defect was found and fixed (DEF-007).** OPAC search counted copies by joining every item in the catalogue. After the fix the query takes 1.0 ms instead of 5.5 ms and uses index scans only, and database CPU under load fell from 64% to 48%. Throughput did not change, because the database was not the bottleneck.

## Conclusion

The prototype meets the latency targets at 10 concurrent users and stays error-free at 50. At 50 users it is limited by running as a single API process. Scaling out requires moving shared state out of that process, which is recorded as DEF-008 (known limitation) and in the production backlog.
