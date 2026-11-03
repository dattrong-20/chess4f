# Delivery status — 2026-11-03

## Verified
- Unified Compose project with persistent Hive/MinIO data retained.
- Published Delta release: r_87d57c48317d40be890a7ec9f6b84047.
- 2,509 games: 1,000 Lichess September + 1,000 October + 509 Chess.com September. 1,990 Lichess games recognized for opening analysis.
- Dagster complete run and unchanged-source no-op verified. No-op preserves publication and skips Spark.
- Trino overview, player profile, replay, historical move habits and C1–C7 aggregate cube verified.
- 24 unit tests; all seven chart paths plus empty filters passed AppTest.
- Empty manual-import source now shows a dedicated message, no None dates or misleading zero cards.
- Native Streamlit theme and source labels deployed in commit 07de6e7; GitHub CI passed: https://github.com/dattrong-20/chess4f/actions/runs/41558392677

## Why 2,000 Lichess games
Each demo month is capped at 1,000 first-matching games. Repeated schedules do not append duplicates or gradually extend this same cap. Increase scope/limit or ingest another month, validate and publish to expand. The scheduled demo cap is not a storage/Trino capacity limit. These samples are not representative of the whole month.

## Remaining, in order
1. Visual review and screenshots/video using a working browser automation runtime. Current browser tool fails to initialize; AppTest is behavioral evidence only.
2. Broader sampled coverage and a coverage ledger before population-level trend claims.
3. Bounded background player synchronization from UI; stronger empty-profile/onboarding flow.
4. Partition-scoped processing, compaction and safe retention for larger backfills.
5. Broader model cohort, calibration and evaluation; current model remains an experimental pregame Elo baseline.
6. Optional live game integration and end-to-end stream validation.

## Runtime
Services require Docker Desktop running. Use scripts/start-demo.ps1; Dagster uses scripts/start-dagster.ps1 on the Windows host. Restarting the PC does not automatically start Dagster. See DEMO.md and ORCHESTRATION.md.
