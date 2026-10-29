from datetime import datetime, timezone

import chess

from .openings import position_key
from .storage import Lake


def records(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def overview(root, source="lichess"):
    lake = Lake(root)
    with lake.connection() as con:
        counts = records(con.execute("""SELECT count(*) games,
            count(opening_family) recognized, count(DISTINCT opening_family) opening_families,
            min(played_at) first_game, max(played_at) last_game FROM silver_games WHERE source=?""",[source]))[0]
        top = records(con.execute("""SELECT opening_family, sum(n_games)::BIGINT n_games,
            100*sum(white_score_sum)/sum(n_games) white_score_pct,
            100*sum(white_wins)/sum(n_games) white_win_pct,
            100*sum(draws)/sum(n_games) draw_pct,
            100*sum(black_wins)/sum(n_games) black_win_pct,
            100*sum(n_games)/sum(sum(n_games)) OVER () popularity_pct
            FROM gold_openings WHERE source=? GROUP BY opening_family ORDER BY n_games DESC""",[source]))
    return {"summary": counts, "openings": top, "source":source,
            "scope": "Rated Blitz, recognized games only for opening charts; imported coverage, not platform-wide population",
            "versions": lake.versions()}


def player_profile(root, source, username):
    with Lake(root).connection() as con:
        parameters = [source, username.lower()]
        summary = records(con.execute("""SELECT count(*) games, sum((outcome='win')::INT) wins,
            sum((outcome='draw')::INT) draws, sum((outcome='loss')::INT) losses,
            100*avg(score) score_pct, min(played_at) first_game, max(played_at) last_game
            FROM gold_player_games WHERE source=? AND player=?""", parameters))[0]
        openings = records(con.execute("""SELECT opening_family, color, speed, count(*) games,
            100*avg(score) score_pct FROM gold_player_games WHERE source=? AND player=?
            GROUP BY ALL ORDER BY games DESC""", parameters))
        opponents = records(con.execute("""SELECT opponent, count(*) games, 100*avg(score) score_pct
            FROM gold_player_games WHERE source=? AND player=? GROUP BY opponent
            ORDER BY games DESC, opponent LIMIT 20""", parameters))
        history = records(con.execute("""SELECT game_key, played_at, opponent, color, speed, rating,
            outcome, opening_family FROM gold_player_games WHERE source=? AND player=?
            ORDER BY played_at DESC LIMIT 200""", parameters))
    return dict(source=source, player=username.lower(), summary=summary,
                openings=openings, opponents=opponents, history=history,
                coverage="Imported games only; not necessarily full platform history")


def game_detail(root, game_key):
    with Lake(root).connection() as con:
        games = records(con.execute("SELECT * FROM silver_games WHERE game_key=?", [game_key]))
        if not games:
            return None
        moves = records(con.execute("SELECT * FROM silver_moves WHERE game_key=? ORDER BY ply", [game_key]))
    return dict(game=games[0], moves=moves)


def move_habits(root, source, username, fen, before, exclude_game=None):
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError("Invalid chess position")
    # An explicit cutoff prevents accidental use of future games in replay.
    cutoff = datetime.fromisoformat(before.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        raise ValueError("before must include timezone")
    cutoff = cutoff.astimezone(timezone.utc).isoformat()
    with Lake(root).connection() as con:
        rows = records(con.execute("""SELECT uci, count(DISTINCT game_key) n_games
            FROM silver_moves WHERE source=? AND player=? AND position_key=?
            AND played_at < ? AND game_key <> ? GROUP BY uci ORDER BY n_games DESC, uci""",
            [source, username.lower(), position_key(board), cutoff, exclude_game or ""]))
    legal = []
    for row in rows:
        move = chess.Move.from_uci(row["uci"])
        if move in board.legal_moves:
            legal.append({**row, "san": board.san(move)})
    total = sum(row["n_games"] for row in legal)
    for row in legal:
        row["frequency_pct"] = 100 * row["n_games"] / total
    return {"kind": "historical_frequency_not_calibrated_prediction", "observations": total,
            "insufficient_history": total < 20, "cutoff": cutoff, "moves": legal,
            "note": "Distinct games per move; a repeating position can contribute to multiple moves. No best-move advice."}
