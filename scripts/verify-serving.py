"""Verify Trino-only serving against local reference; services must be running."""
import math
import os
from pathlib import Path
import chess
import httpx
from streamlit.testing.v1 import AppTest
from chess4f import analytics
from chess4f.config import data_root

api = os.getenv("CHESS4F_API", "http://127.0.0.1:8000")
root = data_root()
with httpx.Client(timeout=180) as client:
    def get(path, params=None):
        response = client.get(api + path, params=params)
        response.raise_for_status()
        return response.json()
    for source in ("lichess", "chesscom", "import"):
        local = analytics.overview(root, source)
        remote = get("/overview", {"source": source})
        assert remote["engine"] == "trino"
        for key in ("games", "recognized", "opening_families"):
            assert local["summary"][key] == remote["summary"][key]
        right = {row["opening_family"]: row for row in remote["openings"]}
        assert len(right) == len(local["openings"])
        for row in local["openings"]:
            for key, value in row.items():
                if key != "opening_family":
                    assert math.isclose(float(value), float(right[row["opening_family"]][key]), abs_tol=1e-8)
    profile = get("/players/chesscom/hikaru")
    assert profile["summary"] == analytics.player_profile(root, "chesscom", "hikaru")["summary"]
    game_key = profile["history"][0]["game_key"]
    game = get(f"/games/{game_key}")
    assert game == analytics.game_detail(root, game_key)
    params = {"fen": chess.STARTING_FEN, "before": game["game"]["played_at"], "exclude_game": game_key}
    assert get("/habits/chesscom/hikaru", params) == analytics.move_habits(root, "chesscom", "hikaru", **params)

app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "apps/dashboard.py"))
app.run(timeout=180)
assert not app.exception and not app.error
assert not any(item.label == "Query engine" for item in app.selectbox)
assert "Dự đoán thử nghiệm" not in app.sidebar.radio[0].options
assert "Truy vết dữ liệu" not in app.sidebar.radio[0].options
app.sidebar.radio[0].set_value("Hồ sơ cá nhân").run(timeout=180)
assert not app.exception and not app.error
print("TRINO_ONLY_OVERVIEW_PROFILE_REPLAY_HABITS_AND_UI_PASSED")
