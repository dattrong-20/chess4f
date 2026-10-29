"""Local Delta transactions; one pipeline writer per data root.

Readers use committed snapshots. Multi-table publication is tracked in run manifests,
not misrepresented as one atomic transaction across all tables.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.dataset as ds
from deltalake import DeltaTable, write_deltalake
from filelock import FileLock


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def digest(text: str):
    return hashlib.sha256(text.encode()).hexdigest()


class Lake:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, name):
        if name not in TABLES:
            raise ValueError("Unknown table")
        return self.root / name

    def exists(self, name):
        return (self.path(name) / "_delta_log").exists()

    def lock(self):
        return FileLock(str(self.root / "pipeline.lock"), timeout=10)

    def upsert(self, name, rows, key):
        if not rows:
            return
        # Last record wins within one microbatch, avoiding ambiguous MERGE matches.
        unique = {r[key]: r for r in rows}
        table = pa.Table.from_pylist(list(unique.values()), schema=TABLES[name])
        path = str(self.path(name))
        if not self.exists(name):
            write_deltalake(path, table)
        else:
            (DeltaTable(path).merge(table, f"t.{key} = s.{key}",
                                   source_alias="s", target_alias="t")
             .when_matched_update_all().when_not_matched_insert_all().execute())

    def overwrite(self, name, table):
        write_deltalake(str(self.path(name)), table, mode="overwrite", schema_mode="overwrite")

    def connection(self):
        con = duckdb.connect()
        con.execute("SET threads=2")
        con.execute("SET memory_limit='1GB'")
        for name, schema in TABLES.items():
            # Read Delta snapshot through delta-rs, never glob obsolete Parquet files.
            # Explicit active-file list from Delta log avoids an Arrow string_view
            # statistics-expression incompatibility after MERGE. These v0.1 tables
            # are unpartitioned, so no virtual partition columns need reconstruction.
            active = DeltaTable(str(self.path(name))).file_uris() if self.exists(name) else []
            if active:
                # DuckDB's native reader handles parquet written after delta-rs MERGE.
                con.read_parquet(active, union_by_name=True).create_view(name.replace("/", "_"))
            else:
                con.register(name.replace("/", "_"), pa.Table.from_pylist([], schema=schema))
        return con

    def versions(self):
        return {name: DeltaTable(str(self.path(name))).version()
                for name in TABLES if self.exists(name)}


def schema(strings=(), integers=(), floats=(), booleans=()):
    return pa.schema([(c, pa.string()) for c in strings] +
                     [(c, pa.int64()) for c in integers] +
                     [(c, pa.float64()) for c in floats] +
                     [(c, pa.bool_()) for c in booleans])


TABLES = {
    "bronze/games": schema(["record_id", "source", "source_uri", "pgn", "run_id", "ingested_at"]),
    "silver/games": schema(
        ["game_key", "source", "game_id", "white", "black", "played_at", "year_month",
         "speed", "result", "opening_eco", "opening_name", "opening_family", "recognition_status",
         "catalog_version", "run_id", "record_id", "source_uri", "time_control", "rating_group"],
        ["white_elo", "black_elo", "ply_count", "matched_ply", "elo_diff"],
        ["avg_elo", "white_score"], ["rated"]),
    "silver/moves": schema(
        ["move_key", "game_key", "source", "player", "played_at", "position_key",
         "uci", "san", "fen_after", "opening_name", "catalog_version"], ["ply"]),
    "silver/quarantine": schema(["record_id", "run_id", "source_uri", "reason"]),
    "gold/openings": schema(
        ["source", "year_month", "speed", "rating_group", "opening_family"],
        ["n_games", "white_wins", "draws", "black_wins"], ["white_score_sum"]),
    "gold/player_games": schema(
        ["source", "player", "opponent", "game_key", "played_at", "year_month", "speed",
         "color", "opening_family", "outcome"], ["rating", "opponent_rating"], ["score"]),
}
