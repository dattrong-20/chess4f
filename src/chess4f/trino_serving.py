"""Read-only adapter for fixed analytics SQL; one published release per request."""
import json
import re
from contextlib import contextmanager
from pathlib import Path

from . import analytics, lakehouse


def bind(query, parameters):
    parts = query.split("?")
    if len(parts) != len(parameters) + 1:
        raise ValueError("Parameter count mismatch")
    result = parts[0]
    for value, part in zip(parameters, parts[1:]):
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError("Expected a text parameter without NUL")
        result += "'" + value.replace("'", "''") + "'" + part
    return result


class Cursor:
    def __init__(self, rows):
        self.columns = list(rows[0]) if rows else []
        self.description = [(name,) for name in self.columns]
        self.rows = [tuple(row[name] for name in self.columns) for row in rows]

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, root):
        path = Path(root) / "published/latest.json"
        self.manifest = json.loads(path.read_text(encoding="utf-8"))
        self.release = lakehouse.release_id(self.manifest["release_id"])

    def execute(self, query, parameters=()):
        tables = {"silver_games": "silver_games", "silver_moves": "silver_moves",
                  "gold_player_games": "spark_player_games"}
        for local, remote in tables.items():
            query = re.sub(r"\b" + local + r"\b", f"chess.{self.release}.{remote}", query)
        return Cursor(lakehouse.sql(bind(query, parameters)))


@contextmanager
def connection(root):
    yield Connection(root)


def player_profile(root, source, username):
    return analytics.player_profile(root, source, username, connection_factory=connection)


def game_detail(root, game_key):
    return analytics.game_detail(root, game_key, connection_factory=connection)


def move_habits(root, source, username, fen, before, exclude_game=None):
    return analytics.move_habits(root, source, username, fen, before, exclude_game,
                                connection_factory=connection)


overview = lakehouse.overview


def opening_cube(root, source, speed="blitz"):
    if source not in ("lichess", "chesscom", "import"):
        raise ValueError("Unknown source")
    if speed not in ("blitz", "rapid", "bullet", "classical", "all"):
        raise ValueError("Unknown speed")
    speed_clause = "" if speed == "all" else " AND speed=?"
    parameters = [source] if speed == "all" else [source, speed]
    with connection(root) as con:
        cursor = con.execute(f"""SELECT year_month, rating_group, speed, opening_family, opening_name,
            count(*) n_games,
            sum(CASE WHEN result='1-0' THEN 1 ELSE 0 END) white_wins,
            sum(CASE WHEN result='1/2-1/2' THEN 1 ELSE 0 END) draws,
            sum(CASE WHEN result='0-1' THEN 1 ELSE 0 END) black_wins
            FROM silver_games WHERE source=? AND rated AND opening_family IS NOT NULL{speed_clause}
            GROUP BY year_month, rating_group, speed, opening_family, opening_name
            ORDER BY year_month, rating_group, speed, opening_family, opening_name""", parameters)
        rows = [dict(zip(cursor.columns, row)) for row in cursor.fetchall()]
        return {"release_id": con.release, "source": source, "speed": speed, "rows": rows}
