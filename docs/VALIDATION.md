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
- Full unit suite after adding coverage-ledger tests was **36 passed**; after the later queue-retry tests the suite is **39 passed** on Windows/Python 3.11. Integration checks below were **not** rerun in this checkpoint because the Docker services and Dagster were stopped; earlier results remain the last recorded integration evidence.
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
- Final unit suite for this checkpoint: **39 passed**.

## 2026-11-03 browser queue no-op check

- Submitted the default backfill scope (Lichess 2026-09 → 2026-10, limit 1,000) through the real Streamlit form with Playwright (`scripts/verify-job-ui.py`). The new request `d767a687976f44f1a38ee03ea1e5233a` was queued and started by the Dagster sensor.
- Both months returned `unchanged_source_validator`, the request finished `complete/published`, and **no new release was published**: the pointer stayed at `r_30c2d4133f144d7394f6825353940801` and Spark/Trino publication was skipped. This exercises the revision-aware skip and the no-op publication guard end to end.
- The earlier full publication path (download → Delta → MinIO → Spark parity → Trino → pointer) remains the evidence recorded above and in the user-jobs sections.

## 2026-11-03 month-input fix

- A Streamlit submission with `2026-7` produced `Invalid isoformat string: '2026-7-01'`. `normalize_month` now accepts `YYYY-M`/`YYYY-MM`, rejects impossible months with a readable message, and is used by `month_plan`, Chess.com and Lichess player collection.
- Deployed by rebuilding the `chess4f:local` image and recreating api/dashboard. Verified inside the running API that `month_plan('2026-7','2026-08')` returns `['2026-07','2026-08']`, and `POST /requests` with `2026-13` returns HTTP 422 `{"detail":"start has an invalid month: '2026-13'"}` instead of a raw `fromisoformat` error.
- The Streamlit error box now prints the API `detail` string rather than the raw JSON envelope. Full suite: **39 passed**.


## 2026-11-03 profile auto-fetch exercised and dataset grown

- The auto-fetch path was exercised with real accounts: Chess.com `hikaru` (6 months), `qbui` and `bodoiheud` (3 months each). They completed through sensor -> collection -> Spark parity -> Trino publication without running an overview backfill first.
- One request (`dambi333`) failed during publication with a Hive Metastore duplicate table registration (`UNIQUETABLE`). That was a real idempotency gap, not a missing account: `register_tables` now re-checks table visibility after a failed `CALL register_table` and only accepts the duplicate when the table exists. Two regression tests cover the tolerated and re-raised paths.
- New published release `r_85d7b319936244558d95a1776b9a1405`: **5,498 games** (2,011 Lichess / 3,487 Chess.com), 440,517 move rows, 696 opening aggregate rows, 10,996 player-perspective rows, 1,000 historical quarantine rows.
- `scripts/verify-serving.py` passed again, and `scripts/verify-openings.py` rendered all C1-C7 views; the Lichess Rated Blitz cube still totals 1,991 games.
- Full unit suite: **44 passed** (includes the two registration-resilience tests).
- Dashboard visual pass: shared `apps/theme.py` palette and layout helper, a WDL donut with a centered game total, consistent hover/legend/grid styling across overview, player profile and C1-C7, and two explanatory captions removed from the overview on request. Screenshots recaptured.

## 2026-11-03 profile search provenance check

- Searching quangbufi returned 203 games, but they came entirely from another player's archive (odoiheud: 197 games, dambi333: 6). Those are opponent rows, not the account's own history; only 12 of them are blitz.
- The sync request covering that period was for qbui, not quangbufi, and returned zero games for every month. The correct fix is to sync the exact username quangbufi.
- Added a Chess.com existence check when a month is empty: a 404 now raises Chess.com username not found instead of completing as an empty month. Two tests cover existing-but-empty and misspelled accounts; suite is 44 passed.

## 2026-11-03 rapid dimension and player provenance

- Gold aggregates, overview and the C1-C7 cube now carry an explicit speed dimension (blitz/rapid/bullet/classical/all). Lichess collection accepts Rated Rapid and `PROCESSOR_VERSION` moved to `3-lichess-rapid`; the Sep/Oct refresh added 267 and 249 rapid games.
- Published release `r_1abbfd6782e24e408845143d6098a665`: **6,014 games** (2,527 Lichess / 3,487 Chess.com), 473,595 move rows, 1,115 opening aggregate rows, 12,028 player-perspective rows. Spark parity and Trino publication passed.
- Verified: `/overview?source=chesscom&speed=rapid` returns 21 opening families; `/openings/cube?source=chesscom&speed=rapid` has 55 rows / 86 rated games; Lichess rapid has 512 recognized games.
- Player profiles now report `own_archive_games` from source URIs, so an account that only appears as an opponent is no longer treated as imported: the UI explains the provenance and the auto-fetch triggers. A misspelled Chess.com username raises "not found" instead of an empty month.
- UI restyle: light chess.com-inspired palette (green accent), card metrics, rounded containers and the classic green board palette for replay/live.
- Full suite: **46 passed**; `verify-serving.py` passed; screenshots recaptured.

## 2026-11-03 T1 hardening: partitions, maintenance, auth, monitoring

- Gold tables are now partitioned by `year_month`, and ingestion rebuilds only the touched month partitions; DuckDB reconstructs partition columns through hive partitioning so snapshots and reference checks keep the column.
- `chess4f compact` compacts active Delta files and performs a retention-bounded vacuum (168-hour floor, dry-run unless `--vacuum`). Verified as a dry run on the Gold tables.
- Re-published release `r_c9809b10d3d14c8c98e4344ee9092a18` after the layout migration: 6,014 games, 1,115 opening aggregates and 12,028 player rows; Spark parity and Trino publication passed.
- Synthetic benchmark: 20,000 games / 120,000 moves in **109.64 s** ingestion and **112.10 s** including snapshot (previous checkpoint: 10,000 games in 44.46 s).
- API operations: optional `CHESS4F_API_TOKEN` on POST/DELETE, `/metrics` request counters plus the published-release gauge, and `/health/deep` checking the pointer and Trino.
- Full suite: **54 passed**; `verify-serving.py` passed on the partitioned release.

## 2026-11-03 100k backfill and clean benchmark

- A user backfill (Lichess 2026-01 to 2026-10, 10,000 games/month) initially stalled because per-batch MERGE rewrote the whole partitioned Silver table. After the partition-scoped upsert fix it resumed and published release `r_54ad767c60d245dbaced09dccf21d3ff`: **103,498 games**, **7,047,128 move rows**, 6,863 opening aggregate rows and 206,996 player-perspective rows, with Spark parity and Trino publication.
- Synthetic benchmark on an idle machine: **100,000 games / 600,000 moves in 562.26 s** ingestion and **565.13 s** including snapshot. The earlier 1,252 s run was contaminated by a concurrent backfill and is not the reference figure.
- `scripts/verify-serving.py` passed on the 103k release; C1-C7 passed and the UI still renders.
- Coverage caveat now stronger: every Lichess month is the first 10,000 matching games, all on that month's first day, so the dataset is ten single-day slices, not ten months of chess.

## 2026-11-03 dambi333 partial-history fix

- `dambi333` showed 7 games because an earlier Chess.com sync ingested only August 2026 before the metastore failure; September (1) and October (12) were never fetched. The Chess.com PubAPI confirms 7 + 1 + 12 = 20.
- Auto-fetch did not fire because the profile already had 7 games from its own archive; the zero-own-games guard does not cover partial history.
- A targeted Chess.com sync for 2026-08..2026-10 added the missing games and published `r_cf01a8750aff4573b0b28fc1e7eff7d4`: 103,511 games, 7,047,963 moves, 3,500 Chess.com games. The profile now reports 20 games (11W / 2D / 7L).

## 2026-11-03 four more Chess.com accounts

- Synced `magnuscarlsen`, `liemle` (Le Quang Liem), `wonderfultime` (Tuan Minh Le) and `duhless` (Daniil Dubov) for 2026-08..2026-10 with a 3,000-game cap each. Accepted 431 / 293 / 1,663 / 1,179 games; 19 Carlsen games were quarantined as nonstandard initial positions (Chess960 variants).
- Published `r_f5e764cd1e4f446485f0210873a82d2b`: 107,023 games (100,011 Lichess / 7,012 Chess.com), 7,361,710 moves, 7,092 opening aggregates, 214,046 player rows. Spark parity and Trino publication passed.
- Profiles: magnuscarlsen 432, liemle 294, wonderfultime 1,697, duhless 1,180 imported games.

## 2026-11-03 dambi333 full-year sync and UI cleanup

- A follow-up Chess.com sync for `dambi333` covering 2026-01..2026-10 completed and published `r_5b43ca80eff54877bfbb5d62e6092757`: 107,155 games (7,144 Chess.com), 7,369,425 moves, 7,174 opening aggregates, 214,310 player rows. The extra 132 games land in March-June.
- Dashboard cleanup: removed the tagline, the "Phạm vi đã nhập" range caption and the opening-analysis "Bản dữ liệu" caption.

## 2026-11-03 final review

- Full unit suite: **54 passed**. scripts/verify-serving.py and scripts/verify-openings.py passed against release 
_5b43ca80eff54877bfbb5d62e6092757 (C1-C7, cube 74,934 recognized blitz games).
- Services checked: API /health and /health/deep ok, Trino ready, Dagster daemon and webserver up, both schedules and the request sensor RUNNING; GitHub Actions badge passing.
- Documentation audit: README links resolve, no TODO/FIXME markers, dataset numbers match the manifest.
- Remaining, explicitly out of the current scope: no-op re-import without republishing, incremental release snapshots, adjacent-month UTC coverage, unattended multi-day operation, HA/TLS/OIDC/backup, and million-game scale tests.

## 2026-11-03 no-op re-import

- Ingestion now compares each game's content hash with the stored `record_id` and `game_key`. Identical games are counted as `unchanged` and skip Bronze/Silver writes, so Delta versions do not move.
- Direct re-import of an existing PGN finished in **3.43 s** with `accepted: 0`, `unchanged: 1` and identical `Lake.versions()`; previously it would have republished the full 412 MB snapshot (~10 min).
- End-to-end queue check: a Chess.com re-sync for `dambi333` 2026-03 completed with `accepted: 0`, `unchanged: 10`; the published release stayed `r_5b43ca80eff54877bfbb5d62e6092757` (no snapshot, no upload, no Spark run).
- Suite: **54 passed**.

## 2026-11-03 incremental release

- The snapshot now clones the previous release table (hardlinks locally), rewrites only months whose local partition signature changed, and appends only new Bronze/quarantine records. Upload uses server-side S3 copy for reused objects and skips already-stored `bronze_objects`.
- First incremental publish of an unchanged dataset: snapshot **3.6 s**, upload **19.5 s** (52 objects copied, 0 uploaded), Spark parity **131.7 s**, Trino publication **67.6 s** — about **3.7 minutes** end to end versus roughly 10 minutes for the previous full snapshot.
- Published `r_e3f3e2f2603b487d89a35c656adb5557` with base `r_5b43ca80eff54877bfbb5d62e6092757`; counts unchanged (107,155 games, 7,369,425 moves) and `verify-serving.py` passed.
- Storage is still duplicated per release: S3 copy creates the objects again (~412 MB/release). Deduplicating or garbage-collecting old releases remains future work; local hardlinks mean no extra disk use locally.
- Suite: **54 passed**.
