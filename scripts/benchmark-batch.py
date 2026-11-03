"""Synthetic bounded-memory ingestion benchmark; never mixes fixtures with real data."""
import argparse
import json
import shutil
import time
from pathlib import Path
from chess4f.pipeline import ingest_pgn
from chess4f.storage import Lake
from chess4f.lakehouse import snapshot

p = argparse.ArgumentParser()
p.add_argument("--games", type=int, default=10000)
args = p.parse_args()
root = Path("artifacts") / f"benchmark-{int(time.time())}"
root.mkdir(parents=True)
shutil.copytree("data/reference/openings", root/"reference/openings")
source = root/"synthetic.pgn"
with source.open("w", encoding="utf-8") as out:
    for n in range(args.games):
        out.write(f'''[Event "Rated Blitz game"]
[Site "https://lichess.org/{n:08x}"]
[UTCDate "2026.09.01"]
[White "benchmark_white"]
[Black "benchmark_black"]
[WhiteElo "1600"]
[BlackElo "1600"]
[TimeControl "180+2"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0

''')
started = time.perf_counter()
run = ingest_pgn(root,source,"lichess")
ingestion_seconds = time.perf_counter()-started
release = snapshot(root)
with Lake(root).connection() as con:
    games = con.execute("SELECT count(*) FROM silver_games").fetchone()[0]
    moves = con.execute("SELECT count(*) FROM silver_moves").fetchone()[0]
assert games == args.games and moves == 6*args.games
assert release["tables"]["silver/games"]["rows"] == games
result = dict(kind="synthetic_short_game_benchmark_not_real_population",games=games,moves=moves,ingestion_seconds=round(ingestion_seconds,2),total_seconds=round(time.perf_counter()-started,2),published=False,root=str(root))
(root/"result.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result))
