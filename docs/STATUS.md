# Delivery status — 2026-11-03

## Verified current functionality
- Unified Compose: MinIO, Hive Metastore, Trino, FastAPI and Streamlit; Spark runs as an on-demand local job. Dagster runs on the host.
- 5,498 unique real games: 2,011 Lichess and 3,487 Chess.com. The initial Lichess monthly sample remains 2,000 games; username syncs (hikaru, qbui, bodoiheud) and live ingestion added the rest. Samples stay bounded per account/month, not platform-wide population estimates.
- Username history sync from both Chess.com and Lichess passed download → Delta → MinIO → Spark comparison → Trino publication. Explicit sync button uses a selected month range and cap, not an unrestricted account crawl.
- Public Lichess game eRIlxQlE was observed through resignation, then automatically queued and published as a finished game. Live updates are source-delayed; Chess.com live is not implemented.
- Published release after first live ingestion: r_79b2a4f399dc48cbad86b447d1c730cc. Re-import checks may produce a newer release without increasing unique counts.
- 44 unit tests passed. Real Trino overview/profile/replay/habits parity and all seven C1–C7 views passed again on 2026-11-03; recognized Rated Blitz cube contains 1,991 games.
- Dagster 1.13.28 webserver/daemon verified running with both schedules and the user-request sensor `RUNNING`.
- Real dashboard screenshots (overview, player profile, opening analysis, delayed live observer) are committed under `docs/images/` and captured with Playwright, not mocked.
- Prediction navigation removed. Traceability navigation hidden; backend retained. Overview no longer displays the internal release ID.
- Gold and snapshot export use Arrow batches. Isolated synthetic 10,000-game / 60,000-move benchmark: 44.46 seconds ingestion, 46.68 seconds including snapshot. This is not a full historical-archive benchmark.

## Limits and future production work
- Source caps and coverage are explicit; no full-month or platform-wide representativeness claim.
- Full Gold/snapshot rewrites remain. Partition-scoped refresh, compaction, retention and million-game/RAM tests remain future work.
- API is localhost-only and has no public-user authentication. Do not expose job submission publicly.
- The PC and Dagster daemon must remain running. Extended unattended operation has not been validated.
- Public Lichess stream is delayed three moves. No engine, outcome prediction or move submission is provided in the UI.

## Reproduce
See USER_JOBS.md, DEMO.md and scripts/capture-demo.py. Re-running the capture writes fresh media to ignored `artifacts/demo`; four representative PNGs are committed in `docs/images/` for the README. Source datasets and secrets are excluded from Git.
