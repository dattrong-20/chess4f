import pytest


@pytest.fixture
def lake_root(tmp_path):
    folder = tmp_path / "reference/openings"
    folder.mkdir(parents=True)
    (folder / "test.tsv").write_text(
        'eco\tname\tpgn\nB20\tSicilian Defense\t1. e4 c5\nC20\tKing\'s Pawn Game\t1. e4 e5\n', encoding="utf-8")
    return tmp_path


def pgn(game_id="AbCd1234", day="2026.09.01", result="1-0", moves="1. e4 c5 2. Nf3 d6"):
    return f'''[Event "Rated Blitz game"]
[Site "https://lichess.org/{game_id}"]
[UTCDate "{day}"]
[UTCTime "12:00:00"]
[White "Alice"]
[Black "Bob"]
[WhiteElo "1600"]
[BlackElo "1500"]
[TimeControl "180+2"]
[Result "{result}"]

{moves} {result}

'''


@pytest.fixture
def pgn_file(lake_root):
    path = lake_root / "test.pgn"
    path.write_text(pgn() + pgn("EfGh5678", "2026.09.02", "0-1", "1. e4 e5"), encoding="utf-8")
    return path
