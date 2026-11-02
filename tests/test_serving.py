import json
import pytest
from fastapi.testclient import TestClient
from chess4f import api, trino_serving


def test_binding_does_not_interpret_parameter_as_sql():
    value = "alice' OR 1=1 -- ?"
    assert trino_serving.bind("SELECT ?", [value]) == "SELECT 'alice'' OR 1=1 -- ?'"
    with pytest.raises(ValueError):
        trino_serving.bind("SELECT ?", [])


def test_connection_pins_release_and_uses_spark_gold(tmp_path, monkeypatch):
    pointer = tmp_path / "published/latest.json"
    pointer.parent.mkdir()
    first, second = "r_" + "a" * 32, "r_" + "b" * 32
    pointer.write_text(json.dumps({"release_id": first}))
    con = trino_serving.Connection(tmp_path)
    pointer.write_text(json.dumps({"release_id": second}))
    queries = []
    monkeypatch.setattr(trino_serving.lakehouse, "sql", lambda q: queries.append(q) or [])
    con.execute("SELECT * FROM gold_player_games WHERE player=?", ["alice"])
    assert f"chess.{first}.spark_player_games" in queries[0]
    assert second not in queries[0]


def test_api_reports_unavailable_without_local_fallback(monkeypatch):
    def unavailable(*args):
        raise RuntimeError("Trino offline")
    monkeypatch.setattr(api, "overview", unavailable)
    response = TestClient(api.app).get("/overview")
    assert response.status_code == 503
