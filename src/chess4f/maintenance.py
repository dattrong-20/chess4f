"""Safe local Delta maintenance: compaction, vacuum and one-time migrations."""
from deltalake import DeltaTable

from .storage import Lake, TABLES

GAME_COLUMNS = [
    "game_key", "source", "game_id", "white", "black", "played_at", "year_month",
    "speed", "result", "opening_eco", "opening_name", "opening_family",
    "recognition_status", "catalog_version", "run_id", "record_id", "source_uri",
    "time_control", "rating_group", "white_elo", "black_elo", "ply_count",
    "matched_ply", "elo_diff", "avg_elo", "white_score", "rated",
]
MOVE_COLUMNS = [
    "move_key", "game_key", "source", "player", "played_at", "position_key",
    "uci", "san", "fen_after", "opening_name", "catalog_version", "ply",
]


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


def partition_silver(root):
    """One-time rewrite of Silver tables partitioned by year_month."""
    lake = Lake(root)
    results = {}
    with lake.connection() as con:
        if lake.exists("silver/games"):
            columns = ", ".join(GAME_COLUMNS)
            rows = con.execute(f"SELECT {columns} FROM silver_games").to_arrow_reader(65536)
            lake.overwrite("silver/games", rows, partition_by=["year_month"])
            results["silver/games"] = lake.partition_columns("silver/games")
        if lake.exists("silver/moves"):
            columns = ("move_key, game_key, source, player, played_at, "
                       "substr(played_at, 1, 7) AS year_month, position_key, uci, san, "
                       "fen_after, opening_name, catalog_version, ply")
            rows = con.execute(f"SELECT {columns} FROM silver_moves").to_arrow_reader(65536)
            lake.overwrite("silver/moves", rows, partition_by=["year_month"])
            results["silver/moves"] = lake.partition_columns("silver/moves")
    return results
