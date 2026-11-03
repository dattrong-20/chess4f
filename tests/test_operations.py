import pytest
from fastapi.testclient import TestClient

from chess4f import api, requests_queue
from chess4f.maintenance import compact
from chess4f.pipeline import ingest_pgn

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
