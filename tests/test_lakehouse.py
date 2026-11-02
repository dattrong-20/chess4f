import json

import pytest
from deltalake import DeltaTable

from chess4f import lakehouse
from chess4f.storage import Lake


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
