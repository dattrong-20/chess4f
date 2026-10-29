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

## Not yet validated

- Large-scale throughput / RAM benchmarks.
- Spark, Trino, object storage and scheduler deployment.
- Real ongoing-game stream integration and recovery.
- Broad-cohort model calibration and predictive accuracy.

Update this document only from executed checks; never mark generated configuration as deployed infrastructure.
