# Unified Compose deployment

All services now belong to the `chess4f` project: API, dashboard, MinIO, Hive Metastore and Trino. Spark and the ingestion CLI are on-demand profile jobs. Dagster runs on the Windows host.

Use `scripts/start-demo.ps1` for startup, or initialize the persistent volume and start services:

```powershell
docker volume create chess4f-lake_metastore
docker compose --env-file .env.lakehouse up -d --no-build
```

The legacy metastore volume name is intentional. It is external, preserved across Compose teardown and reused without copying or resetting the database. MinIO keeps `./data/object-store`; local Delta tables keep `./data`. Do not delete these paths or the volume.

`compose.lakehouse.yaml` is a compatibility include of the unified configuration. Prefer `compose.yaml` in new commands. Credentials remain in ignored `.env.lakehouse`; no secrets are committed. API connects to Trino via internal service DNS (`http://trino:8080`).

For an existing two-project installation, stop and remove only containers labeled `com.docker.compose.project=chess4f-lake` before starting the unified project, without deleting volumes. Never run two Hive instances against the same Derby volume. Other Docker projects must be left untouched.
