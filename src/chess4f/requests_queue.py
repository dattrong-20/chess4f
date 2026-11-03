"""Durable local requests consumed by the host Dagster daemon, never by API threads."""
import json
import re
import subprocess
import uuid
from pathlib import Path

from filelock import FileLock
from .storage import atomic_json, utc_now, Lake
from .sources import month_plan, chesscom_archive, lichess_player
from .pipeline import ingest_pgn
from . import lakehouse


def validate(payload):
    kind = payload.get("kind", "player")
    if kind not in ("player", "backfill", "finished_game"):
        raise ValueError("Unknown job kind")
    if kind == "finished_game":
        from .live import parse_game_id
        return {"kind": kind, "game_id": parse_game_id(payload.get("game_id", ""))}
    source = payload.get("source", "lichess")
    if source not in ("lichess", "chesscom") or (kind == "backfill" and source != "lichess"):
        raise ValueError("Unsupported source")
    months = month_plan(payload["start"], payload["end"])
    if len(months) > 24:
        raise ValueError("Use at most 24 months per request")
    limit = int(payload.get("limit", 1000))
    if not 1 <= limit <= 10000:
        raise ValueError("Limit must be 1–10000 games per month")
    name = payload.get("username", "").strip().lower()
    if kind == "player" and not re.fullmatch(r"[a-z0-9_-]{2,50}", name):
        raise ValueError("Invalid username")
    return dict(kind=kind, source=source, username=name, start=months[0], end=months[-1], limit=limit)


def request_path(root, request_id):
    if not re.fullmatch(r"[a-f0-9]{32}", request_id):
        raise ValueError("Invalid request id")
    return Path(root) / "requests" / f"{request_id}.json"


def enqueue(root, payload):
    payload = validate(payload)
    folder = Path(root) / "requests"
    folder.mkdir(parents=True, exist_ok=True)
    with FileLock(str(folder / "queue.lock"), timeout=5):
        active = []
        for path in folder.glob("*.json"):
            item = json.loads(path.read_text(encoding="utf-8"))
            if item["status"] in ("queued", "running"):
                if item["payload"] == payload:
                    return item
                active.append(item)
        if len(active) >= 20:
            raise ValueError("Queue is full; wait for existing requests")
        item = dict(id=uuid.uuid4().hex, payload=payload, status="queued", stage="waiting_for_dagster", created_at=utc_now(), months=[])
        atomic_json(request_path(root, item["id"]), item)
        return item


def read_request(root, request_id):
    return json.loads(request_path(root, request_id).read_text(encoding="utf-8"))


def process(root, project, request_id, context=None):
    item = read_request(root, request_id)
    if item["status"] == "complete":
        return item
    payload = validate(item["payload"])
    def update(**kwargs):
        item.update(kwargs, updated_at=utc_now())
        atomic_json(request_path(root, request_id), item)
        if context:
            context.log.info(f"Request {request_id}: {item['stage']}")
    try:
        update(status="running", stage="collecting", dagster_run_id=context.run_id if context else None)
        # One host queue job at a time. CLI callers should not publish concurrently.
        with FileLock(str(Path(root) / "request-worker.lock"), timeout=5):
            if payload["kind"] == "finished_game":
                from .sources import lichess_finished
                path, uri = lichess_finished(root, payload["game_id"])
                run = ingest_pgn(root, path, "lichess", source_uri=uri)
                if not run["accepted"]:
                    raise ValueError("Finished game was not accepted")
                item["months"] = [{"run_id": run["run_id"], "accepted": run["accepted"]}]
                journal = Path(root)/"live"/payload["game_id"]/"events.jsonl"
                if journal.exists():
                    import hashlib, shutil
                    checksum = hashlib.sha256(journal.read_bytes()).hexdigest()
                    retained = Path(root)/"bronze_objects"/(checksum+".jsonl")
                    shutil.copyfile(journal,retained)
                    item["raw_event_sha256"] = checksum
            else:
                for month in month_plan(payload["start"], payload["end"]):
                    if any(x.get("month") == month and x.get("status") == "complete" for x in item["months"]):
                        continue
                    update(stage=f"collecting:{month}")
                    if payload["kind"] == "backfill":
                        from .refresh import refresh_months
                        result = refresh_months(root, month, month, payload["limit"])[0]
                        entry = {"month": month, "status": "complete", "result": result["status"], "run_id": result.get("run_id")}
                    else:
                        if payload["source"] == "chesscom":
                            path, uri = chesscom_archive(root, payload["username"], month, allow_empty=True)
                        else:
                            path, uri = lichess_player(root, payload["username"], month, payload["limit"])
                        if path is None:
                            entry = {"month": month, "status": "complete", "accepted": 0, "result": "empty_month"}
                        else:
                            run = ingest_pgn(root, path, payload["source"], limit=payload["limit"], source_uri=uri)
                            if not run["accepted"]:
                                raise ValueError("No games accepted; inspect quarantine")
                            entry = {"month": month, "status": "complete", "accepted": run["accepted"], "run_id": run["run_id"], "limit": payload["limit"], "possibly_limited": run["accepted"] >= payload["limit"]}
                    item["months"].append(entry)
                    update(stage=f"processed:{month}")
            pointer = Path(root) / "published/latest.json"
            existing = json.loads(pointer.read_text()) if pointer.exists() else {}
            if existing.get("source_versions") != Lake(root).versions():
                update(stage="snapshot_upload")
                release = lakehouse.snapshot(root)["release_id"]
                lakehouse.upload(root, project, release)
                update(stage="spark_validation", release_id=release)
                command = ["docker", "compose", "--env-file", ".env.lakehouse", "run", "--rm", "--no-deps", "-e", f"CHESS4F_RELEASE={release}", "spark"]
                result = subprocess.run(command, cwd=project, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
                if result.returncode or f"CHESS4F_SPARK_COMPLETE {release}" not in result.stdout:
                    raise RuntimeError("Spark failed: " + result.stderr[-1500:])
                update(stage="trino_validation")
                lakehouse.validate_publish(root, project, release)
            else:
                item["release_id"] = existing.get("release_id")
            update(status="complete", stage="published", completed_at=utc_now())
    except Exception as exc:
        update(status="failed", stage="failed", error=str(exc)[:2000])
        raise
    return item


def retry_request(root, request_id):
    previous = read_request(root, request_id)
    if previous["status"] != "failed":
        raise ValueError("Only failed requests may be retried")
    new = enqueue(root, previous["payload"])
    # Already active requests keep their own progress.
    if new["status"] == "queued" and not new["months"]:
        new["months"] = previous.get("months", [])
        new["retry_of"] = request_id
        atomic_json(request_path(root,new["id"]),new)
    return new
