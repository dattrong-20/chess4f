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


def month_plan(start, end=None):
    end = end or previous_month()
    first = date.fromisoformat(start + "-01")
    last = date.fromisoformat(end + "-01")
    if first > last:
        raise ValueError("Start month is after end month")
    months = []
    while first <= last:
        months.append(first.strftime("%Y-%m"))
        first = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return months


def chesscom_archive(root, username, month):
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,50}", username):
        raise ValueError("Invalid username")
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
