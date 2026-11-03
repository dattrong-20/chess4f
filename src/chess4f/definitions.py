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

defs = dg.Definitions(jobs=[source_check_job, monthly_refresh_job],
                      schedules=[source_check_schedule, refresh_schedule])
