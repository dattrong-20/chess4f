"""Public documented APIs only. Source availability is never inferred from the calendar."""
import calendar
import io
import re
from datetime import date
from pathlib import Path

import chess.pgn
import httpx
import zstandard

from .config import user_agent
from .storage import atomic_json, utc_now


def previous_month(today=None):
    today = today or date.today()
    return f"{today.year-1}-12" if today.month == 1 else f"{today.year}-{today.month-1:02}"


MONTH_PATTERN = re.compile(r"\s*(\d{4})-(\d{1,2})\s*")


def normalize_month(value, field="month"):
    """Accept YYYY-M / YYYY-MM and return YYYY-MM; reject anything else."""
    match = MONTH_PATTERN.fullmatch(str(value))
    if not match:
        raise ValueError(f"{field} must use YYYY-MM, for example 2026-07")
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        raise ValueError(f"{field} has an invalid month: {value!r}")
    return f"{year:04d}-{month:02d}"


def month_plan(start, end=None):
    end = end or previous_month()
    first = date.fromisoformat(normalize_month(start, "start") + "-01")
    last = date.fromisoformat(normalize_month(end, "end") + "-01")
    if first > last:
        raise ValueError("Start month is after end month")
    months = []
    while first <= last:
        months.append(first.strftime("%Y-%m"))
        first = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return months


def chesscom_archive(root, username, month, allow_empty=False):
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,50}", username):
        raise ValueError("Invalid username")
    month = normalize_month(month)
    date.fromisoformat(month + "-01")
    url = f"https://api.chess.com/pub/player/{username.lower()}/games/{month.replace('-', '/')}"
    folder = Path(root) / "landing/chesscom" / username.lower()
    folder.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=90, headers={"User-Agent": user_agent()}) as client:
        response = client.get(url)
        response.raise_for_status()
    payload = response.json()
    stamp = utc_now().replace(":", "-")
    atomic_json(folder / f"{month}-{stamp}.json", payload)
    games = []
    for item in payload.get("games", []):
        if item.get("pgn"):
            game = chess.pgn.read_game(io.StringIO(item["pgn"]))
            if game is not None:
                game.headers["Rated"] = "true" if item.get("rated") else "false"
                game.headers["TimeClass"] = item.get("time_class", "unknown")
                if item.get("url"):
                    game.headers["Link"] = item["url"]
                games.append(str(game))
    if not games and allow_empty:
        # An empty month is normal for an inactive account, but a misspelled
        # username must not be reported as "no games" and silently skipped.
        with httpx.Client(timeout=30, headers={"User-Agent": user_agent()}) as client:
            profile = client.get(f"https://api.chess.com/pub/player/{username.lower()}")
        if profile.status_code == 404:
            raise ValueError("Chess.com username not found; check the spelling")
        profile.raise_for_status()
        return None, url
    if not games:
        raise ValueError("Source returned no PGNs for this player and month; no fabricated fallback")
    path = folder / f"{month}-{stamp}.pgn"
    path.write_text("\n\n".join(games), encoding="utf-8")
    return path, url


class HeaderFilter(chess.pgn.GameBuilder):
    def __init__(self, day):
        super().__init__()
        self.day = day

    def end_headers(self):
        h = self.game.headers
        if not h.get("UTCDate", h.get("Date", "")).startswith(self.day.replace("-", ".")):
            return chess.pgn.SKIP
        if not re.match(r"^Rated Blitz\b", h.get("Event", "")):
            return chess.pgn.SKIP
        return super().end_headers()


def lichess_day(root, day, limit=1000):
    """Read monthly archive sequentially; capped demo is NOT representative sampling.

    limit=None scans the entire monthly archive to collect all matching-day games.
    Matching the day does not mean the server offers daily downloads.
    """
    date.fromisoformat(day + "-01" if len(day) == 7 else day)
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    month = day[:7]
    url = f"https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst"
    folder = Path(root) / "landing/lichess"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().replace(":", "-")
    path = folder / f"{day}-{stamp}.pgn"
    manifest = dict(source_uri=url, requested_day=day, limit=limit, scanned=0, selected=0,
                    status="running", started_at=utc_now(), selection="first_matching_games" if limit else "all_matching_games")
    meta_path = path.with_suffix(".json")
    atomic_json(meta_path, manifest)
    try:
        with httpx.Client(timeout=httpx.Timeout(120, read=180), follow_redirects=True,
                          headers={"User-Agent": user_agent()}) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                class Reader(io.RawIOBase):
                    def __init__(self):
                        self.chunks = response.iter_bytes()
                        self.pending = b""
                    def readable(self):
                        return True
                    def readinto(self, target):
                        while not self.pending:
                            try:
                                self.pending = next(self.chunks)
                            except StopIteration:
                                return 0
                        n = min(len(target), len(self.pending))
                        target[:n] = self.pending[:n]
                        self.pending = self.pending[n:]
                        return n
                with zstandard.ZstdDecompressor().stream_reader(Reader()) as reader:
                    with io.TextIOWrapper(reader, encoding="utf-8") as text, path.open("w", encoding="utf-8") as out:
                        while True:
                            game = chess.pgn.read_game(text, Visitor=lambda: HeaderFilter(day))
                            if game is None:
                                manifest["status"] = "complete"
                                break
                            manifest["scanned"] += 1
                            h = game.headers
                            if h.get("UTCDate", h.get("Date", "")).startswith(day.replace("-", ".")) and re.match(r"^Rated Blitz\b", h.get("Event", "")):
                                out.write(str(game) + "\n\n")
                                manifest["selected"] += 1
                            if manifest["scanned"] % 10000 == 0:
                                atomic_json(meta_path, manifest)
                            if limit and manifest["selected"] >= limit:
                                manifest["status"] = "limited"
                                break
    except Exception as exc:
        manifest.update(status="failed", error=str(exc))
        raise
    finally:
        manifest["finished_at"] = utc_now()
        atomic_json(meta_path, manifest)
    if not manifest["selected"]:
        raise ValueError("No matching games; inspect source manifest")
    return path, url, manifest


def lichess_player(root, username, month, limit=1000):
    import json
    from datetime import datetime, timezone
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,50}", username):
        raise ValueError("Invalid username")
    month = normalize_month(month)
    first = date.fromisoformat(month + "-01")
    end = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    since = int(datetime.combine(first, datetime.min.time(), timezone.utc).timestamp()*1000)
    until = int(datetime.combine(end, datetime.min.time(), timezone.utc).timestamp()*1000)-1
    uri = f"https://lichess.org/api/games/user/{username.lower()}"
    folder = Path(root) / "landing/players" / username.lower()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (month + "-" + utc_now().replace(":", "-") + ".pgn")
    count = 0
    with httpx.Client(timeout=httpx.Timeout(30, read=180), headers={"User-Agent":user_agent(), "Accept":"application/x-ndjson"}) as client:
        with client.stream("GET", uri, params={"since":since,"until":until,"max":limit,"pgnInJson":"true","ongoing":"false","finished":"true","sort":"dateDesc"}) as response, path.open("w", encoding="utf-8") as out:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("pgn"):
                    out.write(item["pgn"] + "\n\n")
                    count += 1
    return (path if count else None), uri


def lichess_finished(root, game_id):
    from .live import parse_game_id
    game_id = parse_game_id(game_id)
    uri = f"https://lichess.org/game/export/{game_id}"
    with httpx.Client(timeout=60, headers={"User-Agent":user_agent(),"Accept":"application/x-chess-pgn"}) as client:
        response = client.get(uri, params={"evals":"false", "clocks":"false"})
        response.raise_for_status()
    game = chess.pgn.read_game(io.StringIO(response.text))
    if game is None or game.headers.get("Result") not in ("1-0","0-1","1/2-1/2"):
        raise ValueError("Game is not finished; nothing imported")
    folder = Path(root) / "landing/finished"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (game_id + ".pgn")
    path.write_text(response.text, encoding="utf-8")
    return path, uri
