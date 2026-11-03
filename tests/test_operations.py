import pytest
from fastapi.testclient import TestClient

from chess4f import api, requests_queue
from chess4f.maintenance import compact, partition_silver
from chess4f.pipeline import ingest_pgn
from chess4f.storage import Lake
from conftest import pgn

client = TestClient(api.app)


def test_compact_dry_run_and_retention_guard(lake_root, pgn_file):
    ingest_pgn(lake_root, pgn_file, "lichess")
    result = compact(lake_root, ["gold/openings"], retention_hours=168, vacuum=False)
    assert result["gold/openings"]["vacuumed"] is False
    with pytest.raises(ValueError, match="168 hours"):
        compact(lake_root, ["gold/openings"], retention_hours=1, vacuum=False)


def test_metrics_endpoint_counts_requests():
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "chess4f_http_requests_total" in response.text


def test_write_routes_require_token_when_configured(monkeypatch):
    monkeypatch.setenv("CHESS4F_API_TOKEN", "secret")
    monkeypatch.setattr(requests_queue, "enqueue", lambda root, payload: {"id": "fixture"})
    assert client.post("/requests", json={}).status_code == 401
    allowed = client.post("/requests", json={}, headers={"Authorization": "Bearer secret"})
    assert allowed.status_code == 202
    assert allowed.json()["id"] == "fixture"


def test_partition_silver_preserves_rows_and_accepts_new_months(lake_root, pgn_file):
    ingest_pgn(lake_root, pgn_file, "lichess")
    result = partition_silver(lake_root)
    assert result["silver/games"] == ["year_month"]
    assert result["silver/moves"] == ["year_month"]
    pgn_file.write_text(pgn("OcT12345", "2026.10.01"), encoding="utf-8")
    ingest_pgn(lake_root, pgn_file, "lichess")
    lake = Lake(lake_root)
    with lake.connection() as con:
        assert con.execute("SELECT count(*) FROM silver_games").fetchone()[0] == 3
        assert con.execute("SELECT count(*) FROM silver_moves").fetchone()[0] == 10
    assert lake.partition_columns("silver/moves") == ["year_month"]


def test_dashboard_shows_login_when_password_is_set(monkeypatch):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("CHESS4F_DASHBOARD_PASSWORD", "secret")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "apps" / "dashboard.py"))
    app.run(timeout=60)
    assert not app.exception
    assert any(field.label == "Mật khẩu" for field in app.text_input)
