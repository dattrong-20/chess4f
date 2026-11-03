import json
import chess
from chess4f import live


def test_completed_stream_queues_ingestion(lake_root, monkeypatch):
    board=chess.Board();board.push_san("e4");board.push_san("c5")
    events=[{"players":{},"createdAt":1000},{"fen":board.fen(),"lm":"c7c5","wc":100},{"status":{"id":31,"name":"resign"},"winner":"white"}]
    class Stream:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def raise_for_status(self): pass
        def iter_lines(self): return iter(json.dumps(e) for e in events)
    class Client(Stream):
        def __init__(self,*a,**kw): pass
        def stream(self,*a,**kw): return Stream()
    monkeypatch.setattr(live.httpx,"Client",Client)
    result=live.observe(lake_root,"AbCd1234")
    assert result["opening"]["eco"]=="B20"
    assert result["status"]=="stream_closed"
    assert result["created_at_ms"]==1000
    request=json.loads((lake_root/"requests"/(result["ingestion_request_id"]+".json")).read_text())
    assert request["payload"]=={"kind":"finished_game","game_id":"AbCd1234"}
    assert len((lake_root/"live/AbCd1234/events.jsonl").read_text().splitlines())==3


def test_new_lichess_url():
    assert live.parse_game_id("https://lichess.org/game/AbCd1234")=="AbCd1234"
