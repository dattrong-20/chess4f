import json

from fastapi import FastAPI, HTTPException, Query

from .analytics import game_detail, move_habits, overview, player_profile
from .config import data_root
from .live import parse_game_id
from .storage import Lake

app = FastAPI(title="chess4f", version="0.1.0", description="Read-only analytics API. Local-first; no public deployment authentication yet.")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/overview")
def overview_route(source: str = "lichess"):
    return overview(data_root(),source)


@app.get("/players/{source}/{username}")
def player(source: str, username: str):
    return player_profile(data_root(), source, username)


@app.get("/games/{game_key}")
def game(game_key: str):
    result = game_detail(data_root(), game_key)
    if result is None:
        raise HTTPException(404, "Game not imported")
    return result


@app.get("/habits/{source}/{username}")
def habits(source: str, username: str, fen: str, before: str, exclude_game: str | None = None):
    try:
        return move_habits(data_root(), source, username, fen, before, exclude_game)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/live/{game_id}")
def live(game_id: str):
    try:
        game_id = parse_game_id(game_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    path = data_root() / "live" / game_id / "state.json"
    if not path.exists():
        raise HTTPException(404, "Start observer with chess4f live GAME_ID")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/runs")
def runs(limit: int = Query(20, ge=1, le=100)):
    paths = sorted((data_root() / "metadata/runs").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths[:limit]]


@app.get("/model")
def model_report():
    path = data_root()/"models/latest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status":"not_trained"}


@app.get("/prediction")
def prediction(source: str, speed: str, white_elo: int = Query(ge=1,le=4000), black_elo: int = Query(ge=1,le=4000)):
    from .model import predict
    try:
        return predict(data_root(),white_elo,black_elo,source,speed)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
