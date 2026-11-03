import json
import httpx

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .trino_serving import game_detail, move_habits, overview, player_profile, opening_cube
from .config import data_root
from .live import parse_game_id
from .storage import Lake

app = FastAPI(title="chess4f", version="0.1.0", description="Read-only analytics API. Local-first; no public deployment authentication yet.")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/overview")
def overview_route(source: str = "lichess", speed: str = "blitz"):
    if source not in ("lichess", "chesscom", "import"):
        raise HTTPException(422, "Unknown source")
    if speed not in ("blitz", "rapid", "bullet", "classical", "all"):
        raise HTTPException(422, "Unknown speed")
    return overview(data_root(), source, speed)


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
    from .live_service import state
    return state(data_root(), game_id)


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

@app.exception_handler(RuntimeError)
@app.exception_handler(OSError)
@app.exception_handler(httpx.HTTPError)
async def serving_unavailable(request, exc):
    return JSONResponse(status_code=503, content={"detail": "Published lakehouse is unavailable; check Trino and the release pointer."})

@app.get("/openings/cube")
def openings(source: str = "lichess", speed: str = "blitz"):
    try:
        return opening_cube(data_root(), source, speed)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/requests", status_code=202)
def submit_request(payload: dict):
    from .requests_queue import enqueue
    try:
        return enqueue(data_root(), payload)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/requests")
def request_list(limit: int = Query(50, ge=1, le=200)):
    from .requests_queue import list_requests
    return list_requests(data_root(), limit)


@app.get("/requests/{request_id}")
def request_status(request_id: str):
    from .requests_queue import read_request
    try:
        return read_request(data_root(), request_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(404, "Request not found")


@app.get("/live-discovery/{username}")
def live_discovery(username: str):
    from .live_service import discover
    try:
        return discover(username)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/live-observers/{game_id}")
def start_observer(game_id: str):
    from .live_service import start
    try:
        return start(data_root(), game_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.delete("/live-observers/{game_id}")
def stop_observer(game_id: str):
    from .live_service import stop
    try:
        return stop(game_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/requests/{request_id}/retry", status_code=202)
def retry_user_request(request_id: str):
    from .requests_queue import retry_request
    try:
        return retry_request(data_root(), request_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(404, "Request not found")
