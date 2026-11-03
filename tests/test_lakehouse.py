import json

import pyarrow as pa
import pytest
from deltalake import DeltaTable, write_deltalake

from chess4f import lakehouse
from chess4f.storage import TABLES, Lake


def test_snapshot_is_frozen_and_secret_setup_is_idempotent(tmp_path):
    root = tmp_path / "data"
    lake = Lake(root)
    lake.upsert("silver/games", [{"game_key": "import:a", "source": "import"}], "game_key")
    release = lakehouse.snapshot(root)
    lake.upsert("silver/games", [{"game_key": "import:b", "source": "import"}], "game_key")
    frozen = root / "releases" / release["release_id"] / "silver/games"
    assert DeltaTable(str(frozen)).count() == 1
    assert DeltaTable(str(lake.path("silver/games"))).count() == 2
    assert release["source_versions"]["silver/games"] == 0
    assert release["tables"]["silver/games"]["rows"] == 1
    lakehouse.setup(tmp_path)
    first = (tmp_path / ".env.lakehouse").read_bytes()
    lakehouse.setup(tmp_path)
    assert (tmp_path / ".env.lakehouse").read_bytes() == first


def test_failed_parity_never_switches_published_pointer(tmp_path, monkeypatch):
    lake = Lake(tmp_path)
    lake.upsert("silver/games", [{"game_key": "import:a", "source": "import"}], "game_key")
    manifest = lakehouse.snapshot(tmp_path)
    rid = manifest["release_id"]
    manifest["status"] = "uploaded"
    path = tmp_path / "releases" / rid / "manifest.json"
    path.write_text(json.dumps(manifest))
    pointer = tmp_path / "published/latest.json"
    pointer.parent.mkdir()
    pointer.write_text('{"release_id":"old"}')
    def fake_sql(statement):
        if statement.startswith("SHOW TABLES"):
            return []
        if "EXCEPT ALL" in statement:
            return [{"n": 1}]
        if statement.startswith("SELECT count"):
            return [{"n": 1 if statement.endswith(".silver_games") else 0}]
        return []
    monkeypatch.setattr(lakehouse, "sql", fake_sql)
    with pytest.raises(ValueError, match="parity"):
        lakehouse.validate_publish(tmp_path, tmp_path, rid)
    assert json.loads(pointer.read_text())["release_id"] == "old"


def test_release_identifier_rejects_sql_or_path_injection():
    with pytest.raises(ValueError):
        lakehouse.release_id("../other; DROP SCHEMA chess")


def test_register_tables_tolerates_duplicate_after_partial_registration(monkeypatch):
    calls = {"show": 0}

    def fake_sql(statement):
        if statement.startswith("SHOW TABLES"):
            calls["show"] += 1
            # First check sees nothing; after the failed CALL the table exists.
            return [] if calls["show"] == 1 else [{"Table": "gold_openings"}]
        if statement.startswith("CALL"):
            raise RuntimeError("duplicate key value violates unique constraint UNIQUETABLE")
        return []

    monkeypatch.setattr(lakehouse, "sql", fake_sql)
    lakehouse.register_tables("r_" + "a" * 32, {"gold_openings": "gold/openings"})
    assert calls["show"] == 2


def test_register_tables_reraises_when_table_stays_missing(monkeypatch):
    def fake_sql(statement):
        if statement.startswith("SHOW TABLES"):
            return []
        if statement.startswith("CALL"):
            raise RuntimeError("catalog unavailable")
        return []

    monkeypatch.setattr(lakehouse, "sql", fake_sql)
    with pytest.raises(RuntimeError, match="catalog unavailable"):
        lakehouse.register_tables("r_" + "a" * 32, {"gold_openings": "gold/openings"})


def _openings(rows):
    return pa.Table.from_pylist(rows, schema=TABLES["gold/openings"])


def test_incremental_snapshot_reuses_unchanged_partitions(tmp_path):
    root = tmp_path / "data"
    lake = Lake(root)
    lake.upsert("silver/games", [{"game_key": "import:a", "source": "import"}], "game_key")
    september = {"source": "import", "year_month": "2026-09", "speed": "blitz",
                 "rating_group": "1600–1999", "opening_family": "Sicilian Defense",
                 "n_games": 1, "white_wins": 1, "draws": 0, "black_wins": 0, "white_score_sum": 1.0}
    lake.overwrite("gold/openings", _openings([september]), partition_by=["year_month"])
    first = lakehouse.snapshot(root)
    (root / "published").mkdir()
    (root / "published" / "latest.json").write_text(json.dumps(first))

    october = dict(september, year_month="2026-10")
    write_deltalake(str(lake.path("gold/openings")), _openings([october]), mode="overwrite",
                    predicate="year_month = '2026-10'", partition_by=["year_month"])
    second = lakehouse.snapshot(root)

    first_sep = next((root / "releases" / first["release_id"] / "gold/openings").rglob("year_month=2026-09/*.parquet"))
    second_sep = next((root / "releases" / second["release_id"] / "gold/openings").rglob("year_month=2026-09/*.parquet"))
    assert first_sep.stat().st_ino == second_sep.stat().st_ino
    assert second["base_release"] == first["release_id"]
    assert second["tables"]["gold/openings"]["rows"] == 2
    assert DeltaTable(str(root / "releases" / second["release_id"] / "gold/openings")).count() == 2
