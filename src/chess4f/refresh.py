"""Sequential refresh using HTTP validators; publishing is a separate step."""
import json
from pathlib import Path

import httpx
from filelock import FileLock

from .config import user_agent
from .pipeline import ingest_pgn
from .sources import lichess_day, month_plan
from .storage import atomic_json, utc_now


PROCESSOR_VERSION = "2-lichess-game-url"


def probe_month(month):
    url = f"https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst"
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": user_agent()}) as client:
        response = client.head(url)
        if response.status_code == 404:
            return {"available": False, "url": url}
        response.raise_for_status()
        fingerprint = {key: response.headers.get(key) for key in ("etag", "last-modified", "content-length")}
    # Length alone cannot identify a source revision. These are HTTP validators,
    # not a claim that a cryptographic checksum of the full archive was checked.
    usable = bool(fingerprint["etag"] or (fingerprint["last-modified"] and fingerprint["content-length"]))
    return {"available": True, "url": url, "validator": fingerprint if usable else None}


def refresh_months(root, start, end=None, limit=1000, check_only=False):
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    folder = Path(root) / "metadata/refresh"
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    with FileLock(str(folder / "refresh.lock"), timeout=0):
        for month in month_plan(start, end):
            path = folder / f"{month}.json"
            previous = json.loads(path.read_text()) if path.exists() else {}
            attempt = dict(previous, month=month, checked_at=utc_now(), requested_limit=limit)
            try:
                source = probe_month(month)
                attempt["observed_source"] = source
                if not source["available"]:
                    attempt["status"] = "not_yet_available"
                elif (source["validator"] is not None
                      and previous.get("committed_validator") == source["validator"]
                      and "committed_limit" in previous
                      and previous["committed_limit"] == limit
                      and previous.get("processor_version") == PROCESSOR_VERSION):
                    attempt["status"] = "unchanged_source_validator"
                elif check_only:
                    attempt["status"] = "refresh_required"
                else:
                    pgn, uri, selection = lichess_day(root, month, limit)
                    # A source revision during download must not become a skip marker.
                    after = probe_month(month)
                    if not after["available"] or after["validator"] != source["validator"]:
                        raise RuntimeError("Source changed during download; retry before ingestion")
                    run = ingest_pgn(root, pgn, "lichess", source_uri=uri)
                    if run.get("accepted", 0) == 0:
                        raise RuntimeError("No games accepted; inspect ingestion quarantine before committing refresh")
                    attempt.update(processor_version=PROCESSOR_VERSION, status="limited" if limit else "complete_source_scan",
                                   committed_validator=source["validator"], committed_limit=limit,
                                   run_id=run["run_id"], source_manifest=selection,
                                   committed_at=utc_now())
                atomic_json(path, attempt)
                results.append(attempt)
            except Exception as exc:
                # Preserve the last successful revision when a refresh fails.
                attempt.update(status="failed", error=str(exc))
                atomic_json(path, attempt)
                raise
    return results
