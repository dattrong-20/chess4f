import csv
import io
import json
from pathlib import Path

import chess
import chess.pgn
import httpx

from .config import user_agent
from .storage import atomic_json, digest


def position_key(board: chess.Board) -> str:
    # Exclude halfmove/fullmove clocks, preserve turn, castling and legal en-passant.
    return " ".join(board.fen(en_passant="legal").split()[:4])


class OpeningCatalog:
    def __init__(self, directory):
        directory = Path(directory)
        self.lookup = {}
        files = sorted(directory.glob("*.tsv"))
        if not files:
            raise FileNotFoundError("Opening catalog missing; run: chess4f catalog")
        self.version = digest("".join(f.read_text(encoding="utf-8") for f in files))
        for file in files:
            for row in csv.DictReader(io.StringIO(file.read_text(encoding="utf-8")), delimiter="\t"):
                game = chess.pgn.read_game(io.StringIO(row["pgn"]))
                if game is None or game.errors:
                    raise ValueError(f"Invalid opening line in {file.name}")
                board = game.end().board()
                key = position_key(board)
                label = {"eco": row["eco"], "name": row["name"],
                         "family": row["name"].split(":", 1)[0]}
                if key in self.lookup and self.lookup[key] != label:
                    raise ValueError(f"Conflicting opening catalog position: {key}")
                self.lookup[key] = label

    def match(self, board):
        return self.lookup.get(position_key(board))


def download_catalog(root):
    folder = Path(root) / "reference" / "openings"
    folder.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, headers={"User-Agent": user_agent()}, follow_redirects=True) as client:
        # Resolve branch to a commit once; all five files come from the same revision.
        response = client.get("https://api.github.com/repos/lichess-org/chess-openings/commits/master")
        response.raise_for_status()
        revision = response.json()["sha"]
        for letter in "abcde":
            url = f"https://raw.githubusercontent.com/lichess-org/chess-openings/{revision}/{letter}.tsv"
            response = client.get(url)
            response.raise_for_status()
            (folder / f"{letter}.tsv").write_bytes(response.content)
    catalog = OpeningCatalog(folder)
    atomic_json(folder / "manifest.json", {"commit": revision, "catalog_version": catalog.version,
                                          "positions": len(catalog.lookup), "license": "CC0-1.0"})
    return {"positions": len(catalog.lookup), "version": catalog.version, "commit": revision}
