"""Delayed public Lichess observer. The public stream is FEN/lm, not Board API gameState."""
import json
import re
import time
from pathlib import Path

import chess
import httpx

from .config import user_agent
from .openings import OpeningCatalog
from .storage import atomic_json, digest, utc_now


def parse_game_id(value):
    match = re.fullmatch(r"(?:https://lichess\.org/)?([A-Za-z0-9]{8})(?:/(?:white|black))?/?", value.strip())
    if not match:
        raise ValueError("Use an 8-character Lichess game id or public game URL")
    return match.group(1)


class LiveState:
    def __init__(self, game_id, catalog):
        self.catalog = catalog
        self.value = dict(game_id=game_id, source="lichess", status="connecting", opening=None,
                          catalog_version=catalog.version, received_events=0,
                          source_delay="Public API documents a 3-move delay; not instant player assistance")
        self.previous = None

    def apply(self, event):
        fingerprint = digest(json.dumps(event, sort_keys=True))
        if fingerprint == self.previous:
            return False
        self.previous = fingerprint
        self.value["received_events"] += 1
        self.value["received_at"] = utc_now()
        if "fen" in event:
            board = chess.Board(event["fen"])
            if not board.is_valid():
                raise ValueError("Invalid FEN from source")
            label = self.catalog.match(board)
            self.value.update(fen=board.fen(), last_move=event.get("lm"),
                              white_clock=event.get("wc"), black_clock=event.get("bc"),
                              status="observing", current_position_match=label)
            if label:
                self.value["opening"] = label
        if "players" in event:
            self.value["players"] = event["players"]
        if "status" in event:
            self.value["platform_status"] = event["status"]
        if "winner" in event:
            self.value["winner"] = event["winner"]
        return True


def observe(root, game_id, max_events=None):
    game_id = parse_game_id(game_id)
    root = Path(root)
    folder = root / "live" / game_id
    folder.mkdir(parents=True, exist_ok=True)
    catalog = OpeningCatalog(root / "reference/openings")
    state = LiveState(game_id, catalog)
    url = f"https://lichess.org/api/stream/game/{game_id}"
    atomic_json(folder / "state.json", state.value)
    # Bounded retries; raw events allow later replay. No evasion of source delay.
    for attempt in range(4):
        try:
            with httpx.Client(timeout=httpx.Timeout(30, read=180), headers={"User-Agent": user_agent()}) as client:
                with client.stream("GET", url) as response, (folder / "events.jsonl").open("a", encoding="utf-8") as out:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        out.write(json.dumps({"received_at": utc_now(), "event": event}) + "\n")
                        out.flush()
                        if state.apply(event):
                            atomic_json(folder / "state.json", state.value)
                        if max_events and state.value["received_events"] >= max_events:
                            state.value["status"] = "stopped_by_limit"
                            atomic_json(folder / "state.json", state.value)
                            return state.value
            state.value["status"] = "stream_closed"
            break
        except (httpx.HTTPError, ValueError) as exc:
            state.value.update(status="reconnecting", error=str(exc), retry=attempt + 1)
            atomic_json(folder / "state.json", state.value)
            if attempt == 3:
                state.value["status"] = "failed"
                atomic_json(folder / "state.json", state.value)
                raise
            time.sleep(min(2 ** attempt * 2, 15))
    atomic_json(folder / "state.json", state.value)
    return state.value
