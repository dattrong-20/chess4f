# Delivery roadmap — full scope retained

This roadmap separates implemented code from validated deployment. It does not reduce the agreed scope.

## M1 — runnable local slice
- [x] Delta Bronze/Silver/Gold and source-object hashes
- [x] API + player profiles + opening analytics + replay UI
- [x] Stable source IDs, re-import and correction tests
- [x] Lichess September daily integration sample and Chess.com player history
- [x] Personal move frequencies with a historical cutoff
- [x] Experimental pre-game W/D/L model and temporal holdout
- [x] Public Lichess FEN stream receiver and raw journal
- [x] End-to-end live validation on a currently running Lichess game, including finished-game publication
- [x] Docker runtime smoke test: API health, Delta-backed overview and Streamlit health

## M2 — lakehouse integration (single-machine deployment)
- [x] S3-compatible object storage with explicit credentials/secrets handling
- [x] Spark processing job sharing the data contract, matching local gold totals
- [x] Trino + appropriate metastore/catalog, registered Delta tables, SQL comparison
- [x] Controlled Docker profiles fitting 16 GB RAM (Compose `jobs`/`compute`, not simultaneous)
- [x] Snapshot publication: readers consume a coherent run across multiple tables
- [x] Partition strategy / compaction / retention: Silver+Gold by `year_month`, `chess4f compact` with a 168h vacuum floor

## M3 — incremental collection and operations
- [x] Calendar month planner and bounded sequential backfill CLI
- [x] Failed/limited/completed-source-scan registry
- [x] HTTP ETag/revision detection and capped Dagster refresh policy (not a full-archive checksum)
- [ ] Adjacent-source UTC boundary coverage; observed-coverage ledger added (`chess4f coverage`, docs/COVERAGE.md)
- [x] Dagster schedules, bounded read/publication retries, run UI and capped Lichess refresh
- [ ] Additional source quotas and unattended multi-day validation
- [x] Partition-scoped Gold refresh (only touched months are recomputed)
- [x] No-op re-import: identical payloads bump no Delta version and publish no release
- [x] Fresh player sync from UI using bounded Dagster background jobs

## M4 — product and prediction
- [x] Restore all C1–C7 views with explicit filters/denominators; real Trino cube parity and seven AppTest views passed
- [x] Native themed UI, rating trend, coverage notes and final screenshot capture
- Archived experiment only: broader model evaluation is no longer a delivery requirement.
- Out of current scope by user request: position-based prediction; experimental prediction UI removed.
- [ ] Personalized vs population move frequency backoff with uncertainty
- [x] Experimental model limitations documented; no general-accuracy claim

## M5 — live (optional)
- [x] Discover game from username through the documented Lichess endpoint
- [ ] Validate delayed stream reconnect and snapshot catch-up against a real game
- [x] Retain raw event objects and import final PGN with idempotent game keys (not a distributed exactly-once claim)
- [ ] Display observer-only move habits on received positions
- [ ] Kafka integration if it adds replay/consumer value; do not pretend JSONL is Kafka

## GitHub / CV
- [x] Public repository and Linux CI workflow; latest local suite: 53 tests
- [x] Real screenshots committed (`docs/images/`) and Playwright capture scripts; video reproducible locally
- [x] CV description describes only validated capabilities (docs/CV.md)
- [x] Synthetic throughput benchmarks recorded (20k games 110s, 100k games 562s); not a production-scale test
