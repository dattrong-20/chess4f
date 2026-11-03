# Validation log

## Local development — 2026-10-29

- 9 automated tests passed on Windows/Python 3.11 before final UI checks.
- Public repository: https://github.com/dattrong-20/chess4f. Linux CI passed all 9 tests for initial commit `0afa0aa` ([run](https://github.com/dattrong-20/chess4f/actions/runs/40917113988)).
- Docker image built successfully; Compose API healthy, Streamlit health returned `ok`, and the container API read 1,000 Lichess games / 993 recognized / 80 opening families from the existing Delta tables.
- Browser checks: overview rendered real counts; Hikaru profile showed 509 games (422 wins / 43 draws / 44 losses); replay of `chesscom:184627853334` advanced to ply 1 and displayed King's Pawn Game with the next player's historical habits. Model report rendered, and prediction API returned probabilities.
- Real reference: 3,865 positions; commit `712a58be746c143f4ab935b68acc50f4bac813eb`.
- Real data: 1,000 Lichess Rated Blitz games selected from 2026-09-01; 509 Chess.com games in Hikaru's 2026-09 public archive.
- A development import exposed Chess.com PGN differences (`Site=Chess.com`, ID in `Link`, `TimeControl=300`). The parser and regression tests were corrected; initial development rows were rebuilt using stable IDs while prior Delta versions remained recoverable.
- The Arrow/string_view predicate issue after Delta MERGE was resolved by reading active Delta snapshot file URIs through DuckDB's native Parquet reader.

## Experimental model

Scope: Chess.com Blitz in the single-player archive; 309 eligible games. Temporal training: 213 games before 2026-09-23; test: 96 games on/after that date.

| Metric | Model | Class-prior baseline |
|---|---:|---:|
| Log loss | 0.48154 | 0.92034 |
| Multiclass Brier (sum over classes) | 0.23280 | 0.57085 |

These are small-cohort experimental results, **not general chess win-probability performance**. Model features: Elo difference and average Elo. Training rating range: 2545–3452. No independent calibration set. Other users, lower Elo and live board positions are outside demonstrated validity.

## Lakehouse integration checkpoint — 2026-11-01

- Full Windows/Python test suite: 12 passed (45.13 seconds). Includes immutable snapshot, credential setup idempotency, failed-parity pointer preservation, and release-ID validation.
- Existing release `r_d058d9b7ef7f4e1fbe3234c2d1b6684a` is published after verification: 1,509 Silver games, 114,514 moves, 246 local Gold opening rows and 3,018 player perspectives.
- Spark completed successfully for this release: full bidirectional multiset parity passed for openings (246 rows) and player_games (3,018 rows), followed by Delta writes to S3. Trino registered all eight source/output tables, checked source counts and both-direction Gold EXCEPT ALL, then published the release at 2026-11-01T15:43:39Z.

## Serving integration — 2026-11-02

- Docker API returned successful DuckDB and Trino overview queries for lichess (1,000 games), chesscom (509 games), and import (0 games).
- `scripts/verify-serving.py` passed: counts, opening groups and every opening aggregate agree across engines for the published snapshot.
- Streamlit AppTest passed the default view and changing Query engine to trino, with no application exceptions/errors, correct metrics and the published release caption. This is a behavioral test, not a visual-layout review.
- Streamlit HTTP health returned `ok` on localhost:8501.
- Hive restarted successfully using its persisted catalog; release data was retained across service stops.
## Revision-aware refresh and simpler UI — 2026-11-02

- 16 unit/regression tests passed (93.88 seconds).
- Real header-only probes confirmed September/October archive availability; no source PGN download was performed by this check.
- AppTest passed with Trino as the default and the engine control inside the technical sidebar expander; switching to DuckDB and back also passed.
- Source refresh uses HTTP validators and scope checkpoints. Recurring scheduling and partition-scoped Gold updates remain outstanding.
## Not yet validated

- Large-scale throughput / RAM benchmarks.
- Automated scheduler deployment, partition-scoped refresh and multi-node operation.
- Real ongoing-game stream integration and recovery.
- Broad-cohort model calibration and predictive accuracy.

Update this document only from executed checks; never mark generated configuration as deployed infrastructure.


## 2026-11-03 unified Compose and October recovery

- Project `chess4f` now contains all application/lakehouse Docker services. Legacy external Hive volume and MinIO bind data retained.
- October sample initially quarantined 1,000 games because Site URLs contained `/game/ID`. Parser now accepts both supported URL shapes with stable game identity. Reimport accepted 1,000 and quarantined 0. Historical failed-quality run remains recorded.
- Clean rows: Lichess September 1,000 + October 1,000; Chess.com September 509. First-match samples are not representative of monthly populations.
- Dagster run `ca7aed44-2668-4b81-a494-f423ef61a26a` succeeded. Published release `r_87d57c48317d40be890a7ec9f6b84047`; Spark parity: 455 opening aggregate rows and 5,018 player-perspective rows.
- 24 unit tests passed. Serving integration passed on the new release: overview/profile/replay/habits and Streamlit AppTest.
- Model artifact remains the earlier small-sample pregame experiment, not a live board evaluation model. No expanded model-performance claim is made from the new ingestion.

- `scripts/verify-openings.py` passed all C1–C7 views, empty-filter handling, and Trino cube count/outcome invariants: 1,990 recognized Rated Blitz Lichess games.

- Player profile UI: AppTest verified Hikaru 509-game KPIs, four chart panels, explicit 200-row history coverage, and an unknown-player empty state. Ratings are shown separately by speed; no rating series is pooled across time controls.

## 2026-11-03 committed user jobs, live ingestion and coverage ledger

- Commits `e4ccb4f` (feature) and `e9dd525` (docs) publish the player-sync, monthly backfill, finished-game ingestion queue and live observer work that was previously uncommitted, then push to `main`.
- Full unit suite after adding coverage-ledger tests was **36 passed**; after the later queue-retry tests the suite is **38 passed** on Windows/Python 3.11. Integration checks below were **not** rerun in this checkpoint because the Docker services and Dagster were stopped; earlier results remain the last recorded integration evidence.
- `chess4f coverage` against the published local dataset (`r_30c2d4133f144d7394f6825353940801`) reports:
  - Lichess, 2,011 games: 2026-09 has 1,000 games all on one day (cap 1,000); 2026-10 has 1,010 games (1,000 on 1 October + 10 on 31 October); 2026-11 has 1 game from a completed live observation.
  - Chess.com, 519 games: 2026-09 has 509 games over 21 days (4 on 30 September); 2026-10 has 10 games.
  - Consequence: month-over-month opening comparisons are illustrative, not monthly population estimates. The September Lichess sample is single-day.
- Deprecated `fetch_record_batch` calls were replaced with DuckDB `to_arrow_reader`; no behavior change is claimed beyond the API migration.
- Not revalidated in this checkpoint: Trino serving, Streamlit AppTest, release republication and browser screenshots.

## 2026-11-03 integration re-verification and screenshots

With the Docker stack already running and the host Dagster restarted through `scripts/start-dagster.ps1`:

- API `/overview?source=lichess` returned 2,011 games and 97 opening families from Trino release `r_30c2d4133f144d7394f6825353940801`; Streamlit `/_stcore/health` returned `ok`.
- `scripts/verify-serving.py` passed: `TRINO_ONLY_OVERVIEW_PROFILE_REPLAY_HABITS_AND_UI_PASSED`. This re-checks overview parity for all three sources, Hikaru profile/replay/habits and the absence of the prediction/traceability navigation.
- `scripts/verify-openings.py` passed every C1–C7 view plus empty-filter handling; the Trino cube totals match 1,991 recognized Rated Blitz games.
- Dagster 1.13.28 webserver and daemon are running; `source_check_job_schedule` (`0 7 * * *`), `monthly_refresh_job_schedule` (`0 8 * * 0`) and `user_request_sensor` all report `RUNNING`.
- `scripts/capture-demo.py` captured the real dashboard in headless Chromium: overview, player profile, live observer, backfill form and opening analysis. Four screenshots were committed to `docs/images/` and embedded in the README; video and extra captures remain in ignored `artifacts/demo`.
- Not re-run in this pass: a scheduled refresh, and any multi-day unattended run.
- Final unit suite for this checkpoint: **38 passed**.

## 2026-11-03 browser queue no-op check

- Submitted the default backfill scope (Lichess 2026-09 → 2026-10, limit 1,000) through the real Streamlit form with Playwright (`scripts/verify-job-ui.py`). The new request `d767a687976f44f1a38ee03ea1e5233a` was queued and started by the Dagster sensor.
- Both months returned `unchanged_source_validator`, the request finished `complete/published`, and **no new release was published**: the pointer stayed at `r_30c2d4133f144d7394f6825353940801` and Spark/Trino publication was skipped. This exercises the revision-aware skip and the no-op publication guard end to end.
- The earlier full publication path (download → Delta → MinIO → Spark parity → Trino → pointer) remains the evidence recorded above and in the user-jobs sections.

