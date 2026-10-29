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
- [ ] End-to-end live validation on a currently running game
- [x] Docker runtime smoke test: API health, Delta-backed overview and Streamlit health

## M2 — distributed lakehouse integration
- [ ] S3-compatible object storage with explicit credentials/secrets handling
- [ ] Spark processing job sharing the data contract, matching local gold totals
- [ ] Trino + appropriate metastore/catalog, registered Delta tables, SQL comparison
- [ ] Controlled Docker profiles fitting 16 GB RAM (jobs need not run simultaneously)
- [ ] Snapshot publication: readers consume a coherent run across multiple tables
- [ ] Partition strategy / compaction / retention without destroying required snapshots

## M3 — incremental collection and operations
- [x] Calendar month planner and bounded sequential backfill CLI
- [x] Failed/limited/completed-source-scan registry
- [ ] Source ETag/checksum change detection, automated refresh policy
- [ ] Adjacent-source UTC boundary coverage and coverage ledger
- [ ] Scheduler, retry/backoff policy, run dashboard and source-specific quotas
- [ ] Efficient no-op re-import and partition-scoped gold refresh
- [ ] Fresh player sync from UI using bounded background jobs

## M4 — product and prediction
- [ ] Restore all C1–C7 views with explicit filters/denominators
- [ ] Better UI, rating trend and source coverage indicators
- [ ] Broader training cohort; calibration and stronger temporal/group evaluation
- [ ] Position-based outcome model (separate from pre-game baseline)
- [ ] Personalized vs population move frequency backoff with uncertainty
- [ ] Do not publish performance claims from the elite-player sample as general accuracy

## M5 — live (optional)
- [ ] Discover game from username through a supported documented endpoint
- [ ] Validate delayed stream reconnect and snapshot catch-up against a real game
- [ ] Persist events to lakehouse; import final result exactly once
- [ ] Display observer-only move habits on received positions
- [ ] Kafka integration if it adds replay/consumer value; do not pretend JSONL is Kafka

## GitHub / CV
- [x] Public repository push and Linux CI result (9 tests passed)
- [ ] Screenshots and reproducible demonstration recording
- [ ] CV description describes only validated capabilities
- [ ] Benchmark actual throughput, latency, memory and recovery behavior
