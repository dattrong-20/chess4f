import chess
from fastapi.testclient import TestClient

from chess4f.analytics import game_detail, move_habits, overview, player_profile
from chess4f.api import app
from chess4f.live import LiveState, parse_game_id
from chess4f.openings import OpeningCatalog
from chess4f.pipeline import ingest_pgn, classify_speed
from chess4f.sources import month_plan, previous_month
from chess4f.storage import Lake
from datetime import date
from conftest import pgn
import pytest


def test_repeat_ingest_is_idempotent(lake_root, pgn_file):
    a = ingest_pgn(lake_root, pgn_file, "lichess")
    b = ingest_pgn(lake_root, pgn_file, "lichess")
    assert a["status"] == b["status"] == "complete"
    assert overview(lake_root)["summary"]["games"] == 2
    with Lake(lake_root).connection() as con:
        assert con.execute("SELECT count(*) FROM silver_moves").fetchone()[0] == 6
        assert con.execute("SELECT count(*) FROM bronze_games").fetchone()[0] == 2
        assert con.execute("SELECT count(*) FROM gold_player_games").fetchone()[0] == 4
    assert player_profile(lake_root, "lichess", "ALICE")["summary"]["wins"] == 1
    assert sum(r["popularity_pct"] for r in overview(lake_root)["openings"]) == pytest.approx(100)


def test_date_filter_and_quarantine(lake_root, pgn_file):
    with pgn_file.open("a", encoding="utf-8") as f:
        f.write(pgn("IjKl9012", result="*"))
    report = ingest_pgn(lake_root, pgn_file, "lichess", start="2026-09-02", end="2026-09-02")
    assert report["accepted"] == report["filtered"] == report["quarantined"] == 1
    assert overview(lake_root)["summary"]["games"] == 1


def test_correction_removes_old_move_tail(lake_root, pgn_file):
    ingest_pgn(lake_root, pgn_file, "lichess")
    pgn_file.write_text(pgn(moves="1. e4 c5"), encoding="utf-8")
    ingest_pgn(lake_root, pgn_file, "lichess")
    assert len(game_detail(lake_root, "lichess:AbCd1234")["moves"]) == 2


def test_habits_exclude_future_and_current_game(lake_root, pgn_file):
    ingest_pgn(lake_root, pgn_file, "lichess")
    args = [lake_root,"lichess","alice",chess.STARTING_FEN]
    assert move_habits(*args, "2026-09-01T12:00:00+00:00")["observations"] == 0
    assert move_habits(*args, "2026-09-03T00:00:00+00:00", "lichess:AbCd1234")["observations"] == 1


def test_live_uses_public_fen_events(lake_root):
    state = LiveState("AbCd1234", OpeningCatalog(lake_root / "reference/openings"))
    board = chess.Board(); board.push_san("e4"); board.push_san("c5")
    event = {"fen":board.fen(),"lm":"c7c5","wc":180,"bc":180}
    assert state.apply(event)
    assert state.value["opening"]["eco"] == "B20"
    assert not state.apply(event)
    assert parse_game_id("https://lichess.org/AbCd1234") == "AbCd1234"
    with pytest.raises(ValueError):
        parse_game_id("https://localhost/private")


def test_calendar_boundaries():
    assert previous_month(date(2026,1,2)) == "2025-12"
    assert month_plan("2025-12", "2026-02") == ["2025-12","2026-01","2026-02"]
    assert classify_speed("300") == "blitz"


def test_month_input_accepts_unpadded_month():
    assert month_plan("2026-7", "2026-08") == ["2026-07", "2026-08"]
    assert month_plan(" 2026-7 ", "2026-07") == ["2026-07"]
    with pytest.raises(ValueError, match="invalid month"):
        month_plan("2026-13")
    with pytest.raises(ValueError, match="YYYY-MM"):
        month_plan("2026/07")


def test_chesscom_link_is_stable_id(lake_root,pgn_file):
    raw=pgn().replace('[Site "https://lichess.org/AbCd1234"]','[Site "Chess.com"]\n[Link "https://www.chess.com/game/live/123456789"]')
    pgn_file.write_text(raw,encoding="utf-8")
    ingest_pgn(lake_root,pgn_file,"chesscom")
    pgn_file.write_text(raw.replace('[Event "Rated Blitz game"]','[Event "Rated Blitz game"]\n[Rated "true"]'),encoding="utf-8")
    ingest_pgn(lake_root,pgn_file,"chesscom")
    assert overview(lake_root,"chesscom")["summary"]["games"] == 1
    assert overview(lake_root,"lichess")["summary"]["games"] == 0
    assert game_detail(lake_root,"chesscom:123456789") is not None


def test_api_contract_with_local_fixture(lake_root, pgn_file, monkeypatch):
    monkeypatch.setenv("CHESS4F_DATA", str(lake_root))
    ingest_pgn(lake_root, pgn_file, "lichess")
    from chess4f import api, analytics
    for name in ("player_profile", "game_detail", "move_habits"):
        monkeypatch.setattr(api, name, getattr(analytics, name))
    monkeypatch.setattr(api, "overview", lambda root, source, speed: analytics.overview(root, source))
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/overview").json()["summary"]["games"] == 2
    assert client.get("/games/missing").status_code == 404
    assert client.get("/players/lichess/alice").json()["summary"]["games"] == 2


def test_lichess_game_url_and_legacy_url_share_identity(lake_root, pgn_file):
    ingest_pgn(lake_root, pgn_file, "lichess")
    pgn_file.write_text(pgn_file.read_text().replace("lichess.org/", "lichess.org/game/"))
    run = ingest_pgn(lake_root, pgn_file, "lichess")
    assert run["accepted"] == 2 and run["quarantined"] == 0
    assert overview(lake_root)["summary"]["games"] == 2


def test_rapid_games_reach_gold_aggregates(lake_root, pgn_file):
    rapid = pgn("RaPiD123").replace('[TimeControl "180+2"]', '[TimeControl "600+0"]')
    rapid = rapid.replace('[Event "Rated Blitz game"]', '[Event "Rated Rapid game"]')
    pgn_file.write_text(rapid, encoding="utf-8")
    ingest_pgn(lake_root, pgn_file, "lichess")
    with Lake(lake_root).connection() as con:
        speeds = dict(con.execute("SELECT speed, count(*) FROM gold_openings GROUP BY speed").fetchall())
    assert speeds.get("rapid") == 1
    assert "blitz" not in speeds


def test_player_profile_separates_own_archive_from_opponent_rows(lake_root, pgn_file):
    ingest_pgn(lake_root, pgn_file, "lichess", source_uri="https://lichess.org/api/games/user/alice")
    profile = player_profile(lake_root, "lichess", "alice")
    assert profile["summary"]["own_archive_games"] == 2
    opponent = player_profile(lake_root, "lichess", "bob")
    assert opponent["summary"]["games"] == 2
    assert opponent["summary"]["own_archive_games"] == 0
