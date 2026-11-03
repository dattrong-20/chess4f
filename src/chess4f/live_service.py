"""Bounded public observer threads. No engine evaluation or move submission."""
import threading
from pathlib import Path
import json
import re
import httpx

from .live import observe, parse_game_id
from .config import user_agent

_lock = threading.Lock()
_observers = {}


def discover(username):
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,50}", username):
        raise ValueError("Invalid username")
    with httpx.Client(timeout=30, headers={"Accept":"application/json", "User-Agent":user_agent()}) as client:
        response = client.get(f"https://lichess.org/api/user/{username}/current-game", params={"evals":"false"})
        response.raise_for_status()
    item = response.json()
    status = item.get("status")
    ongoing = status in ("started", "created", 10, 20)
    return {"game_id": item.get("id"), "ongoing": ongoing, "status": status, "players": item.get("players")}


def start(root, game_id):
    game_id = parse_game_id(game_id)
    with _lock:
        running = _observers.get(game_id)
        if running and running[0].is_alive():
            return {"game_id":game_id,"status":"already_observing"}
        if sum(thread.is_alive() for thread, event in _observers.values()) >= 2:
            raise ValueError("At most two live observers; stop one first")
        event = threading.Event()
        def run():
            try:
                observe(root, game_id, stop_event=event)
            except Exception:
                pass  # observe persists failure state for the UI
        thread = threading.Thread(target=run, daemon=True, name=f"observer-{game_id}")
        _observers[game_id] = (thread,event)
        thread.start()
    return {"game_id":game_id,"status":"connecting"}


def stop(game_id):
    game_id = parse_game_id(game_id)
    with _lock:
        running = _observers.get(game_id)
        if running:
            running[1].set()
    return {"game_id":game_id,"status":"stop_requested"}


def state(root, game_id):
    game_id = parse_game_id(game_id)
    path = Path(root)/"live"/game_id/"state.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    with _lock:
        running = _observers.get(game_id)
        alive = bool(running and running[0].is_alive())
    result["receiver_running"] = alive
    if not alive and result.get("status") in ("observing","connecting","reconnecting"):
        result["status"] = "disconnected"
    return result
