import io
import json
import re
import uuid
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

import chess
import chess.pgn
from deltalake import DeltaTable

from .openings import OpeningCatalog, position_key
from .storage import Lake, atomic_json, digest, utc_now


def classify_speed(value):
    try:
        base, increment = map(int, (value if "+" in value else value + "+0").split("+"))
        seconds = base + 40 * increment
        return "bullet" if seconds < 180 else "blitz" if seconds < 480 else "rapid" if seconds < 1500 else "classical"
    except (ValueError, AttributeError):
        return "unknown"


def transform(game, source, source_uri, run_id, record_id, catalog):
    h = game.headers
    if game.errors:
        raise ValueError("invalid_moves")
    if h.get("Variant", "Standard") not in ("Standard", "Chess") or game.board().fen() != chess.STARTING_FEN:
        raise ValueError("nonstandard_initial_position")
    result = h.get("Result")
    if result not in ("1-0", "0-1", "1/2-1/2"):
        raise ValueError("unfinished_or_invalid_result")
    try:
        date = datetime.strptime(h.get("UTCDate") or h.get("Date", ""), "%Y.%m.%d")
        time = h.get("UTCTime", "00:00:00")
        played_at = datetime.strptime(date.strftime("%Y-%m-%d") + " " + time,
                                      "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
    except ValueError as exc:
        raise ValueError("invalid_date") from exc
    white, black = h.get("White", "").strip().lower(), h.get("Black", "").strip().lower()
    if white in ("", "?") or black in ("", "?"):
        raise ValueError("missing_player")
    def elo(key):
        try:
            n = int(h.get(key, ""))
            return n if n > 0 else None
        except ValueError:
            return None
    we, be = elo("WhiteElo"), elo("BlackElo")
    site = h.get("Link", "") if source == "chesscom" else h.get("Site", "")
    site = site or h.get("Site", "")
    patterns = {"lichess": r"https?://(?:www\.)?lichess\.org/([A-Za-z0-9]{8})(?:[/?#]|$)",
                "chesscom": r"https?://(?:www\.)?chess\.com/game/(?:live|daily)/(\d+)(?:[/?#]|$)"}
    match = re.search(patterns.get(source, r"(?!)"), site)
    if source in ("lichess", "chesscom") and not match:
        raise ValueError("missing_platform_game_id")
    # Identical content id for imported PGNs lacking a platform id; explicitly source-scoped.
    game_id = match.group(1) if match else record_id
    game_key = f"{source}:{game_id}"
    board = game.board()
    opening = None
    matched_ply = 0
    moves = []
    for ply, move in enumerate(game.mainline_moves(), 1):
        before = position_key(board)
        san = board.san(move)
        player = white if board.turn else black
        board.push(move)
        if ply <= 36:
            label = catalog.match(board)
            if label:
                opening, matched_ply = label, ply
        moves.append(dict(move_key=f"{game_key}:{ply}", game_key=game_key, source=source,
                          player=player, played_at=played_at, position_key=before, uci=move.uci(),
                          san=san, fen_after=board.fen(), ply=ply,
                          opening_name=opening["name"] if opening else None, catalog_version=catalog.version))
    avg = (we + be) / 2 if we is not None and be is not None else None
    group = "unknown" if avg is None else "<1200" if avg < 1200 else "1200–1599" if avg < 1600 else "1600–1999" if avg < 2000 else "≥2000"
    row = dict(game_key=game_key, source=source, game_id=game_id, white=white, black=black,
               played_at=played_at, year_month=played_at[:7], speed=h.get("TimeClass") or classify_speed(h.get("TimeControl")),
               result=result, opening_eco=opening["eco"] if opening else None,
               opening_name=opening["name"] if opening else None,
               opening_family=opening["family"] if opening else None,
               recognition_status="matched" if opening else "no_catalog_match",
               catalog_version=catalog.version, run_id=run_id, record_id=record_id,
               source_uri=source_uri, time_control=h.get("TimeControl", "?"),
               rating_group=group, white_elo=we, black_elo=be, ply_count=len(moves),
               matched_ply=matched_ply, elo_diff=we-be if avg is not None else None,
               avg_elo=avg, white_score={"1-0": 1., "0-1": 0., "1/2-1/2": .5}[result],
               rated=(h["Rated"].lower() == "true") if "Rated" in h else
                     ("rated" in h.get("Event", "").lower() and "unrated" not in h.get("Event", "").lower()))
    return row, moves


def rebuild_gold(lake):
    with lake.connection() as con:
        openings = con.execute("""
            SELECT source, year_month, speed, rating_group, opening_family,
                   count(*)::BIGINT n_games,
                   sum((result='1-0')::INTEGER)::BIGINT white_wins,
                   sum((result='1/2-1/2')::INTEGER)::BIGINT draws,
                   sum((result='0-1')::INTEGER)::BIGINT black_wins,
                   sum(white_score)::DOUBLE white_score_sum
            FROM silver_games WHERE rated AND speed='blitz' AND opening_family IS NOT NULL
            GROUP BY ALL
        """).fetch_arrow_table()
        players = con.execute("""
            SELECT source, white player, black opponent, game_key, played_at, year_month, speed,
                   'white' color, opening_family,
                   CASE white_score WHEN 1 THEN 'win' WHEN 0 THEN 'loss' ELSE 'draw' END outcome,
                   white_elo rating, black_elo opponent_rating, white_score score FROM silver_games
            UNION ALL
            SELECT source, black, white, game_key, played_at, year_month, speed,
                   'black', opening_family,
                   CASE white_score WHEN 0 THEN 'win' WHEN 1 THEN 'loss' ELSE 'draw' END,
                   black_elo, white_elo, 1-white_score FROM silver_games
        """).fetch_arrow_table()
    lake.overwrite("gold/openings", openings)
    lake.overwrite("gold/player_games", players)


def ingest_pgn(root, path, source="import", start=None, end=None, limit=None, source_uri=None):
    if source not in ("lichess", "chesscom", "import"):
        raise ValueError("Invalid platform")
    if start and end and start > end:
        raise ValueError("start must be <= end")
    lake = Lake(root)
    catalog = OpeningCatalog(Path(root) / "reference/openings")
    run_id = uuid.uuid4().hex
    origin = source_uri or str(Path(path).resolve())
    hasher = hashlib.sha256()
    with open(path, "rb") as original:
        for block in iter(lambda: original.read(1024 * 1024), b""):
            hasher.update(block)
    source_hash = hasher.hexdigest()
    original_path = Path(root) / "bronze_objects" / f"{source_hash}.pgn"
    original_path.parent.mkdir(parents=True, exist_ok=True)
    if not original_path.exists():
        shutil.copyfile(path, original_path)
    report = dict(run_id=run_id, source=source, source_uri=origin, started_at=utc_now(),
                  status="running", read=0, selected=0, accepted=0, quarantined=0,
                  filtered=0, catalog_version=catalog.version, start=start, end=end, limit=limit,
                  source_sha256=source_hash, original_object=str(original_path))
    report_path = Path(root) / "metadata/runs" / f"{run_id}.json"
    atomic_json(report_path, report)
    bronze, clean, moves, bad = [], [], [], []
    def flush():
        lake.upsert("bronze/games", bronze, "record_id")
        lake.upsert("silver/quarantine", bad, "record_id")
        if clean and lake.exists("silver/moves"):
            # Remove obsolete tail moves when an upstream game is corrected/re-imported.
            keys = ",".join("'" + r["game_key"].replace("'", "''") + "'" for r in clean)
            DeltaTable(str(lake.path("silver/moves"))).delete(f"game_key IN ({keys})")
        lake.upsert("silver/games", clean, "game_key")
        lake.upsert("silver/moves", moves, "move_key")
        bronze.clear(); clean.clear(); moves.clear(); bad.clear()
    try:
        with lake.lock(), open(path, encoding="utf-8-sig") as stream:
            while True:
                game = chess.pgn.read_game(stream)
                if game is None:
                    break
                report["read"] += 1
                raw = game.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=False))
                record_id = digest(source + "|" + raw)
                bronze.append(dict(record_id=record_id, source=source, source_uri=origin,
                                   pgn=raw, run_id=run_id, ingested_at=utc_now()))
                try:
                    row, game_moves = transform(game, source, origin, run_id, record_id, catalog)
                    day = row["played_at"][:10]
                    if (start and day < start) or (end and day > end):
                        report["filtered"] += 1
                    else:
                        clean.append(row); moves.extend(game_moves)
                        report["accepted"] += 1
                        report["selected"] += 1
                except ValueError as exc:
                    bad.append(dict(record_id=record_id, run_id=run_id, source_uri=origin, reason=str(exc)))
                    report["quarantined"] += 1
                if report["read"] % 200 == 0:
                    flush()
                    atomic_json(report_path, report)
                if limit and report["accepted"] >= limit:
                    report["status"] = "limited"
                    break
            flush()
            rebuild_gold(lake)
            report["status"] = "complete" if report["status"] == "running" else report["status"]
            report["versions"] = lake.versions()
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        report["finished_at"] = utc_now()
        atomic_json(report_path, report)
    return report
