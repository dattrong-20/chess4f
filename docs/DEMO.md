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
2. Overview: choose Lichess (2,011 games at this checkpoint) then Chess.com (519 games). Explain sample coverage, source separation and the distinction between source samples. These numbers describe the documented demo, not a fixed application limit.
3. Opening analysis: show C1, C3 and C4; change month/Elo filters and sample threshold. Explain white score = wins + half draws divided by games. Show C2/C7 as two observed sample months, not a reliable long-term trend. Export one CSV.
4. Player profile: chesscom / hikaru. Show results, opponents and openings. Copy one game key into the replay screen; show historical habits and the insufficient-history message where applicable.
5. Player sync: expand the download form, choose months and a cap, then submit. Show durable queued/running/published status. Requests can take minutes while Spark/Trino validate.
6. Dagster: show successful run ca7aed44-2668-4b81-a494-f423ef61a26a and its four steps. Explain that publication only follows Spark and Trino validation. Show schedules/timezone and capped ingestion.
7. Live observer: use a current public Lichess game ID, connect and observe board/opening updates. Explain the source delay. The final game is automatically queued for ingestion. The old traceability screen is hidden; historical manifests remain retained.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify-serving.py
.\.venv\Scripts\python.exe scripts/verify-openings.py
```

Integration checks need running services and local Delta data matching the published release. AppTest verifies behavior, not visual screenshot quality.

## Remaining boundaries

MinIO hosts immutable published Delta releases; ingestion still stages local Delta before publication. Dagster is single-host SQLite. No automatic OS startup or high availability is claimed. Live observation and finished-game publication were validated with eRIlxQlE; Chess.com live is not supported. Partition-scoped processing and full historical coverage remain roadmap items. Prediction is excluded from the requested UI.

## Capture real browser evidence
```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[demo]'
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/capture-demo.py
.\.venv\Scripts\python.exe scripts/capture-live-demo.py
```
The first script uses retained live state (set CHESS4F_DEMO_GAME if needed). The second chooses a currently broadcast public Blitz game and records 30 seconds; source availability/move timing can make that assertion fail. Outputs are in artifacts/demo.
