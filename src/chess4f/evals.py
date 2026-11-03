"""Engine evaluations recovered from Lichess PGN comments (local cache).

Lichess archives annotate moves with `[%eval ...]`. Chess.com PGNs do not, so
this cache only covers Lichess games; the UI must label it accordingly.
"""
import re
import sqlite3
from pathlib import Path

import chess.pgn

EVAL_RE = re.compile(r"\[%eval\s+(#?-?\d+(?:\.\d+)?)\]")
SITE_RE = re.compile(r"https?://(?:www\.)?lichess\.org/(?:game/)?([A-Za-z0-9]{8})")


def parse_eval(comment):
    """Return (centipawns, mate) or None. Positive values favour White."""
    match = EVAL_RE.search(comment or "")
    if not match:
        return None
    raw = match.group(1)
    if raw.startswith("#"):
        try:
            return None, int(raw[1:])
        except ValueError:
            return None
    try:
        return round(float(raw) * 100), None
    except ValueError:
        return None


def database(root):
    path = Path(root) / "evals.sqlite"
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE IF NOT EXISTS evals (
        game_key TEXT, ply INTEGER, cp INTEGER, mate INTEGER,
        PRIMARY KEY (game_key, ply))""")
    return con


def series(con, game_key):
    rows = con.execute("SELECT ply, cp, mate FROM evals WHERE game_key=? ORDER BY ply",
                       (game_key,)).fetchall()
    return [{"ply": ply, "cp": cp, "mate": mate} for ply, cp, mate in rows]


def pgn_files(root):
    root = Path(root)
    files = list((root / "landing/lichess").glob("*.pgn"))
    files += list((root / "landing/players").glob("**/*.pgn"))
    files += list((root / "landing/finished").glob("*.pgn"))
    return sorted(files)


def backfill(root, progress=None):
    """Scan retained Lichess PGNs and store per-ply evals for matching games."""
    con = database(root)
    games = stored = 0
    files = pgn_files(root)
    for path in files:
        with path.open(encoding="utf-8-sig", errors="replace") as stream:
            while True:
                game = chess.pgn.read_game(stream)
                if game is None:
                    break
                games += 1
                match = SITE_RE.search(game.headers.get("Site", "") or "")
                if not match:
                    continue
                game_key = f"lichess:{match.group(1)}"
                rows = []
                for ply, node in enumerate(game.mainline(), 1):
                    parsed = parse_eval(node.comment)
                    if parsed:
                        rows.append((game_key, ply, parsed[0], parsed[1]))
                if rows:
                    con.executemany("INSERT OR REPLACE INTO evals VALUES (?,?,?,?)", rows)
                    stored += 1
        con.commit()
        if progress:
            progress(path.name, games, stored)
    con.commit()
    con.close()
    return {"games_scanned": games, "games_with_eval": stored, "files": len(files)}
