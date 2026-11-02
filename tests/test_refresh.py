import json

import pytest

from chess4f import refresh


def configure(monkeypatch):
    revision = {"value": "v1"}
    calls = []
    monkeypatch.setattr(refresh, "probe_month", lambda month: {"available": True, "url": "fixture", "validator": {"etag": revision["value"]}})
    monkeypatch.setattr(refresh, "lichess_day", lambda *args: ("fixture.pgn", "fixture", {"status": "limited"}))
    def ingest(*args, **kwargs):
        calls.append(1)
        return {"run_id": str(len(calls))}
    monkeypatch.setattr(refresh, "ingest_pgn", ingest)
    return revision, calls


def test_skip_same_revision_but_refresh_changed_scope_and_revision(tmp_path, monkeypatch):
    revision, calls = configure(monkeypatch)
    refresh.refresh_months(tmp_path, "2026-09", "2026-09", 100)
    assert refresh.refresh_months(tmp_path, "2026-09", "2026-09", 100)[0]["status"] == "unchanged_source_validator"
    assert len(calls) == 1
    refresh.refresh_months(tmp_path, "2026-09", "2026-09", 200)
    revision["value"] = "v2"
    refresh.refresh_months(tmp_path, "2026-09", "2026-09", 200)
    assert len(calls) == 3


def test_check_only_never_marks_data_imported(tmp_path, monkeypatch):
    _, calls = configure(monkeypatch)
    report = refresh.refresh_months(tmp_path, "2026-09", "2026-09", check_only=True)[0]
    assert report["status"] == "refresh_required"
    assert "committed_validator" not in report and not calls
    monkeypatch.setattr(refresh, "probe_month", lambda month: {"available": False})
    assert refresh.refresh_months(tmp_path, "2026-09", "2026-09")[0]["status"] == "not_yet_available"
    assert not calls


def test_failure_preserves_previous_success(tmp_path, monkeypatch):
    revision, _ = configure(monkeypatch)
    refresh.refresh_months(tmp_path, "2026-09", "2026-09")
    revision["value"] = "v2"
    def fail(*args, **kwargs):
        raise RuntimeError("fixture failure")
    monkeypatch.setattr(refresh, "ingest_pgn", fail)
    with pytest.raises(RuntimeError):
        refresh.refresh_months(tmp_path, "2026-09", "2026-09")
    checkpoint = json.loads((tmp_path / "metadata/refresh/2026-09.json").read_text())
    assert checkpoint["status"] == "failed"
    assert checkpoint["committed_validator"] == {"etag": "v1"}


def test_revision_change_mid_download_not_ingested(tmp_path, monkeypatch):
    _, calls = configure(monkeypatch)
    responses = iter([{"available": True, "validator": "v1"}, {"available": True, "validator": "v2"}])
    monkeypatch.setattr(refresh, "probe_month", lambda month: next(responses))
    with pytest.raises(RuntimeError, match="changed during download"):
        refresh.refresh_months(tmp_path, "2026-09", "2026-09")
    assert not calls
