"""Safe local Delta maintenance: compaction and retention-bounded vacuum."""
from deltalake import DeltaTable

from .storage import Lake, TABLES


def compact(root, tables=None, retention_hours=168, vacuum=False):
    """Compact active files and optionally vacuum beyond the retention window."""
    if retention_hours < 168:
        raise ValueError("Retention must be at least 168 hours (Delta default)")
    lake = Lake(root)
    results = {}
    for name in tables or list(TABLES):
        if name not in TABLES:
            raise ValueError(f"Unknown table: {name}")
        if not lake.exists(name):
            continue
        table = DeltaTable(str(lake.path(name)))
        table.optimize.compact()
        removed = table.vacuum(retention_hours=retention_hours, dry_run=not vacuum,
                               enforce_retention_duration=True)
        results[name] = {"vacuum_files": len(removed), "vacuumed": vacuum,
                         "retention_hours": retention_hours}
    return results
