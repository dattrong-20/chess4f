# Dagster orchestration and Trino-only serving

Dagster OSS 1.13.28 runs on the Windows host and invokes the existing Docker Spark job. Its UI is http://127.0.0.1:3000/. The persistent instance is `data/dagster` (SQLite, logs, run history); this is a single-machine deployment, not a highly available production cluster.

## Start

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev,lakehouse,orchestration]'
.\scripts\start-demo.ps1
.\scripts\start-dagster.ps1
```

Docker, the lakehouse services, and Dagster daemon must remain running. Closing the web browser does not stop the daemon. Shutting down the PC stops execution; automatic Windows login/startup is not installed by these scripts. Do not start a second instance against the same database.

## Jobs and schedules

| Job | Schedule (Asia/Barnaul, UTC+7) | Action |
|---|---|---|
| source_check_job | Every day 07:00 | HEAD-only availability/revision check for previous calendar month |
| monthly_refresh_job | Sunday 08:00 | At most 1,000 matching Rated Blitz/Rapid games of previous month, then release pipeline if local versions changed |

Schedules default to RUNNING. The Dagster UI can pause them or launch a manual run. One queued run executes at a time. A manual month uses config `ops.collect_source.config.month: "2026-10"`; `limit` must be 1–5,000. This selects an integration sample, not a representative monthly population. Full archive backfill remains an explicitly invoked CLI operation.

The refresh job graph is:

```text
collect_source -> prepare_release -> spark_gold -> publish_release
```

Collection invokes the tested Python parser/Delta pipeline. Preparation creates an immutable snapshot and uploads it. Spark independently computes Gold and checks parity. Publication registers/validates the tables through Trino and changes the serving pointer only after validation. Gold and published-release materializations include the release ID. If source is unavailable or local versions already match the published release, downstream work is skipped inside the steps.

Only read-only source checks and publication have bounded retries. Spark and uploads are not blindly retried onto partially written immutable paths: rerun the entire job to allocate a new release. A failed job leaves the previously published serving pointer intact. The run queue limits Dagster runs; it does not prevent a user from separately starting CLI work. Avoid simultaneous manual pipeline runs.

On Windows, structured Dagster step events/run metadata are available even when compute stdout capture is disabled. Do not enable PYTHONLEGACYWINDOWSSTDIO for this setup: the local validation encountered a capture startup hang. Spark stdout is explicitly attached to the step log.

## Application queries

The public API serves overview, profiles, replay and historical move habits through Trino only. Each multi-query request pins the release ID at entry. There is no query-engine control in the dashboard and no silent DuckDB fallback on a Trino failure. Model artifacts, live-state JSON and run manifests remain filesystem artifacts, not analytical table queries.

DuckDB remains an internal transformation/training/reference dependency. It is not removed from ingestion; replacing that processing implementation is a separate scope from moving application serving to Trino.

## CV wording

After validating the deployed run: "Built a chess lakehouse with Delta/S3, Spark transformations, Trino analytical serving and Dagster scheduled orchestration, immutable release publication and data parity checks."

Do not describe this machine as a multi-node Spark cluster, claim full-platform coverage from the capped sample, or describe the optional live receiver as a validated real-time prediction system.