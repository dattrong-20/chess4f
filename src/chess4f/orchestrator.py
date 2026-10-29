"""Sequential backfill runner with explicit scope and completion registry.

Source-file completion is NOT complete UTC-month coverage (boundary spillover).
"""
import json
from pathlib import Path

from .pipeline import ingest_pgn
from .sources import lichess_day, month_plan
from .storage import atomic_json, utc_now


def sync_months(root, start, end=None, limit=1000, force=False):
    registry = Path(root) / "metadata/months"
    registry.mkdir(parents=True, exist_ok=True)
    results = []
    for month in month_plan(start,end):
        checkpoint = registry / f"{month}.json"
        if checkpoint.exists() and not force:
            previous = json.loads(checkpoint.read_text(encoding="utf-8"))
            if previous.get("status") == "complete_source_scan":
                results.append({"month":month,"status":"skipped_complete_source_scan"})
                continue
        status = {"month":month,"started_at":utc_now(),"status":"running","limit":limit,
                  "scope":"Rated Blitz with matching UTC month within this one source file; boundary spillover not backfilled"}
        atomic_json(checkpoint,status)
        try:
            path,uri,source = lichess_day(root,month,limit)
            run = ingest_pgn(root,path,"lichess",source_uri=uri)
            status.update(status="limited" if limit else "complete_source_scan",run_id=run["run_id"],
                          source_manifest=source)
        except Exception as exc:
            status.update(status="failed",error=str(exc))
            raise
        finally:
            status["finished_at"] = utc_now()
            atomic_json(checkpoint,status)
        results.append(status)
    return results
