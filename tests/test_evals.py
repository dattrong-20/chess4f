from pathlib import Path

from chess4f.evals import backfill, database, parse_eval, series


def test_parse_eval_variants():
    assert parse_eval("[%eval 0.17] [%clk 0:03:00]") == (17, None)
    assert parse_eval("[%eval -0.4]") == (-40, None)
    assert parse_eval("[%eval #8]") == (None, 8)
    assert parse_eval("[%eval #-3]") == (None, -3)
    assert parse_eval("[%clk 0:03:00]") is None


def test_backfill_reads_lichess_comments(tmp_path):
    folder = tmp_path / "landing" / "lichess"
    folder.mkdir(parents=True)
    (folder / "sample.pgn").write_text("""[Event "Rated Blitz game"]
[Site "https://lichess.org/AbCd1234"]
[White "alice"]
[Black "bob"]
[Result "1-0"]

1. e4 { [%eval 0.17] } e5 { [%eval 0.22] } 2. Nf3 { [%eval 0.1] } 1-0

""", encoding="utf-8")
    result = backfill(tmp_path)
    assert result["games_with_eval"] == 1
    con = database(tmp_path)
    rows = series(con, "lichess:AbCd1234")
    con.close()
    assert [row["ply"] for row in rows] == [1, 2, 3]
    assert rows[0]["cp"] == 17
