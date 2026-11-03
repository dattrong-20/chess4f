# Reproducible demonstration

## Start and prerequisites

Use Python 3.11, Docker Desktop Linux engine and the dependency extras described in ORCHESTRATION.md. Run setup and collection/publication per LAKEHOUSE.md for a fresh checkout; Git does not contain data or credentials. For this existing installation:

```powershell
.\scripts\start-demo.ps1
.\scripts\start-dagster.ps1
```

If Dagster is already running, use the existing instance; do not launch a duplicate. Dashboard: http://127.0.0.1:8501/ ; Dagster: http://127.0.0.1:3000/ .

## Demo sequence and screenshots

1. Docker Desktop: one chess4f group, separate services. Capture healthy API and Trino. Spark is an on-demand job, not an always-running cluster.
2. Overview: choose Lichess (2,000 games) then Chess.com (509 games). Explain sample coverage, source separation and published release ID. These numbers describe the documented demo, not a fixed application limit.
3. Opening analysis: show C1, C3 and C4; change month/Elo filters and sample threshold. Explain white score = wins + half draws divided by games. Show C2/C7 as two observed sample months, not a reliable long-term trend. Export one CSV.
4. Player profile: chesscom / hikaru. Show results, opponents and openings. Copy one game key into the replay screen; show historical habits and the insufficient-history message where applicable.
5. Experimental prediction: show held-out evaluation and prior baseline, explain the elite-player sample and pregame Elo-only inputs. Do not claim live position evaluation or general calibration.
6. Dagster: show successful run ca7aed44-2668-4b81-a494-f423ef61a26a and its four steps. Explain that publication only follows Spark and Trino validation. Show schedules/timezone and capped ingestion.
7. Traceability: show the October parser failure in the historical run manifest and successful reprocessing. No raw failure evidence was erased.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify-serving.py
.\.venv\Scripts\python.exe scripts/verify-openings.py
```

Integration checks need running services and local Delta data matching the published release. AppTest verifies behavior, not visual screenshot quality.

## Remaining boundaries

MinIO hosts immutable published Delta releases; ingestion still stages local Delta before publication. Dagster is single-host SQLite. No automatic OS startup or high availability is claimed. Live observation is optional and not yet validated end-to-end against a current game. Broader cohort modeling, partition-scoped processing and full historical coverage remain roadmap items.
