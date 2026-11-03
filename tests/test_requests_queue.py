import pytest
from chess4f import requests_queue as queue


def payload(**kwargs):
    return dict(kind="player", source="lichess", username="tester", start="2026-09", end="2026-10", limit=10, **kwargs)


def test_queue_deduplicates_active_request(tmp_path):
    first = queue.enqueue(tmp_path, payload())
    assert queue.enqueue(tmp_path, payload())["id"] == first["id"]
    assert queue.read_request(tmp_path, first["id"])["status"] == "queued"
    with pytest.raises(ValueError):
        queue.read_request(tmp_path, "../../secret")


@pytest.mark.parametrize("field,value", [("username","../x"),("source","http://localhost"),("limit",0),("end","2030-01")])
def test_queue_validates_scope(tmp_path, field, value):
    item = payload()
    item[field] = value
    with pytest.raises(ValueError):
        queue.enqueue(tmp_path, item)


def test_failed_collection_never_publishes(tmp_path, monkeypatch):
    request = queue.enqueue(tmp_path, payload())
    def fail(*a, **kw):
        raise RuntimeError("fixture source failure")
    monkeypatch.setattr(queue, "lichess_player", fail)
    monkeypatch.setattr(queue.lakehouse, "snapshot", lambda *a: pytest.fail("must not publish"))
    with pytest.raises(RuntimeError):
        queue.process(tmp_path, tmp_path, request["id"])
    assert queue.read_request(tmp_path, request["id"])["status"] == "failed"


def test_empty_player_months_complete_without_publication(tmp_path, monkeypatch):
    from chess4f.storage import atomic_json
    atomic_json(tmp_path/"published/latest.json", {"source_versions":{}, "release_id":"fixture"})
    request = queue.enqueue(tmp_path, payload())
    monkeypatch.setattr(queue,"lichess_player",lambda *a: (None,"fixture"))
    monkeypatch.setattr(queue.lakehouse,"snapshot",lambda *a: pytest.fail("unchanged data"))
    result = queue.process(tmp_path,tmp_path,request["id"])
    assert result["status"] == "complete"
    assert len(result["months"]) == 2
    assert all(item["accepted"] == 0 for item in result["months"])
