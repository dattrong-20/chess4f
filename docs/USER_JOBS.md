# Player sync, backfill and delayed live observation

## Start
Run `scripts/start-demo.ps1` and `scripts/start-dagster.ps1`. The API writes validated requests to `data/requests`; a default-running Dagster sensor checks every 15 seconds and launches one queued job at a time. Docker socket access is not exposed to the API container. This local deployment has no public-user authentication; do not expose its write endpoints to the internet.

## Player history
In Player profile, choose Chess.com or Lichess, enter a username and expand the sync form. Choose up to 24 months and 1–10,000 games per month. The action downloads public completed games, ingests stable source IDs, rebuilds Gold, uploads a release, checks Spark parity, validates Trino and only then switches the serving pointer. Search alone remains read-only; the explicit sync button performs the download. Monthly caps are not claims of complete account history.

**Automatic fetch.** With the "Tự động tải lịch sử nếu tài khoản chưa có" checkbox on (default), a profile with no games from its own archive triggers one bounded download automatically (appearing only as an opponent is not enough): the three most recent complete months at 1,000 games/month, through the same queue → Spark → Trino → publish path. It does not require running the overview backfill first, and it only fires once per (source, username) until the profile has data. For a different range or a larger cap, use the manual form. The download still takes minutes because it publishes a validated release; it cannot show the profile instantly.

Re-syncing months whose games are already stored completes with `accepted: 0` and no new release (identical PGNs are detected by record hash). Empty months are recorded for existing accounts; a misspelled Chess.com username is now reported as "username not found" instead of being silently treated as an empty month. Failures retain completed-month progress; Retry creates a new Dagster run and resumes remaining months. A failed publication leaves the prior release serving. HTTP 429/source errors are shown rather than bypassing provider limits. The host/daemon must remain on. API restart does not erase queued files.

## Historical backfill
The data-import page submits sequential monthly Lichess requests. Revision and parser-version checkpoints avoid repeating unchanged scopes. For an explicit uncapped source scan use the existing `chess4f sync-months --start YYYY-MM --end YYYY-MM --all` CLI outside active jobs, then publish. Full archives can take substantial time/storage; no million-game performance claim has been validated.

PGN parsing and Delta ingestion are batched; Gold and release export now use Arrow record batches rather than loading every table into Python RAM. A separate synthetic benchmark of 10,000 short games/60,000 moves took 44.46 seconds ingestion and 46.68 seconds including snapshot on this machine. Synthetic short-game timing is not an estimate for full historical archives. Partition-scoped rewriting/retention optimization remains future work.

## Live
Use a public Lichess game ID, or discover an ongoing game by username, then Connect. At most two observers run per API process, each bounded to six hours. Public updates are delayed by Lichess (three moves); this is not instant player assistance, an engine or a move-submission client. Stop is checked on the next source line/heartbeat. API restart disconnects observers; reconnect explicitly.

The stream records raw NDJSON, validates FEN and keeps the last recognized opening in the first 36 plies. Finished games are queued for PGN ingestion/publication, using stable game IDs to avoid duplicate analytical rows. Completed raw event journals are retained by content hash and uploaded with the release. Chess.com live-move streaming is not implemented; use Chess.com for completed history and Lichess for public live observation.

Official contracts: https://lichess-org.github.io/api/ and https://support.chess.com/en/articles/9650547-what-is-the-pubapi-and-how-do-i-use-it

## Screenshots/video
Run `python scripts/capture-demo.py` after installing the optional Playwright development tool and Chromium. Outputs go to ignored `artifacts/demo`. Capture uses a separate headless browser and real API data, not mocked screens. Use a currently observed game ID for live captures.
