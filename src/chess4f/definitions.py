"""Dagster orchestration on the Windows host; Spark runs in Docker."""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import dagster as dg

from .config import data_root
from . import lakehouse
from .refresh import refresh_months
from .sources import previous_month
from .storage import Lake

PROJECT = Path(os.getenv("CHESS4F_PROJECT", Path(__file__).resolve().parents[2]))
ZONE = "Asia/Barnaul"


class RefreshConfig(dg.Config):
    month: str = ""
    limit: int = 1000


def month_value(value):
    return value or previous_month(datetime.now(ZoneInfo(ZONE)).date())


@dg.op(retry_policy=dg.RetryPolicy(max_retries=2, delay=60))
def inspect_source(context, config: RefreshConfig):
    month = month_value(config.month)
    result = refresh_months(data_root(), month, month, config.limit, check_only=True)
    context.add_output_metadata({"month": month, "report": dg.MetadataValue.json(result)})
    return result


@dg.op
def collect_source(context, config: RefreshConfig):
    if not 1 <= config.limit <= 5000:
        raise ValueError("Scheduled demo limit must be between 1 and 5000")
    month = month_value(config.month)
    result = refresh_months(data_root(), month, month, config.limit)
    context.add_output_metadata({"month": month, "report": dg.MetadataValue.json(result)})
    return result


@dg.op
def prepare_release(context, source_report):
    if any(item["status"] == "not_yet_available" for item in source_report):
        context.log.info("Source not published yet; keep the existing serving release.")
        return None
    root = data_root()
    pointer = root / "published/latest.json"
    if pointer.exists():
        published = json.loads(pointer.read_text())
        if published["source_versions"] == Lake(root).versions():
            context.log.info("Local Delta versions already published; no new Spark run needed.")
            return None
    release = lakehouse.snapshot(root)
    lakehouse.upload(root, PROJECT, release["release_id"])
    context.add_output_metadata({"release_id": release["release_id"]})
    return release["release_id"]


@dg.op
def spark_gold(context, release):
    if release is None:
        return None
    command = ["docker", "compose", "--env-file", ".env.lakehouse", "-f", "compose.yaml",
               "run", "--rm", "--no-deps", "-e", f"CHESS4F_RELEASE={lakehouse.release_id(release)}", "spark"]
    result = subprocess.run(command, cwd=PROJECT, text=True, encoding="utf-8", errors="replace",
                            capture_output=True, timeout=1800)
    context.log.info(result.stdout[-12000:])
    if result.returncode:
        raise RuntimeError("Spark failed: " + result.stderr[-6000:])
    if f"CHESS4F_SPARK_COMPLETE {release}" not in result.stdout:
        raise RuntimeError("Spark completion marker missing")
    context.log_event(dg.AssetMaterialization(asset_key="spark_gold", metadata={"release_id": release}))
    return release


@dg.op(retry_policy=dg.RetryPolicy(max_retries=2, delay=30))
def publish_release(context, release):
    if release is None:
        return {"status": "unchanged"}
    manifest = lakehouse.validate_publish(data_root(), PROJECT, release)
    context.log_event(dg.AssetMaterialization(asset_key="published_lakehouse",
        metadata={"release_id": release, "counts": dg.MetadataValue.json(manifest["trino_counts"])}))
    return manifest


@dg.job(executor_def=dg.in_process_executor)
def source_check_job():
    inspect_source()


@dg.job(executor_def=dg.in_process_executor)
def monthly_refresh_job():
    publish_release(spark_gold(prepare_release(collect_source())))


# Checks are cheap; ingestion is capped and sequential. No full-month scan on a timer.
source_check_schedule = dg.ScheduleDefinition(job=source_check_job, cron_schedule="0 7 * * *",
    execution_timezone=ZONE, default_status=dg.DefaultScheduleStatus.RUNNING)
refresh_schedule = dg.ScheduleDefinition(job=monthly_refresh_job, cron_schedule="0 8 * * 0",
    execution_timezone=ZONE, default_status=dg.DefaultScheduleStatus.RUNNING)

class RequestConfig(dg.Config):
    request_id: str


@dg.op
def process_user_request(context, config: RequestConfig):
    from .requests_queue import process
    return process(data_root(), PROJECT, config.request_id, context)


@dg.job(executor_def=dg.in_process_executor)
def user_request_job():
    process_user_request()


@dg.sensor(job=user_request_job, minimum_interval_seconds=15, default_status=dg.DefaultSensorStatus.RUNNING)
def user_request_sensor(context):
    folder = data_root() / "requests"
    for path in sorted(folder.glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if item["status"] == "running" and item.get("dagster_run_id"):
            run = context.instance.get_run_by_id(item["dagster_run_id"])
            if run and run.is_finished and not run.is_success:
                from .storage import atomic_json, utc_now
                item.update(status="failed",stage="failed",error="Dagster run interrupted; retry resumes completed months",updated_at=utc_now())
                atomic_json(path,item)
        if item["status"] == "queued":
            yield dg.RunRequest(run_key=item["id"], run_config={"ops":{"process_user_request":{"config":{"request_id":item["id"]}}}})


defs = dg.Definitions(jobs=[source_check_job, monthly_refresh_job, user_request_job], sensors=[user_request_sensor],
                      schedules=[source_check_schedule, refresh_schedule])
