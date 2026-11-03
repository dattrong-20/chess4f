"""Real Trino cube parity and all seven Streamlit chart views."""
import sys
from pathlib import Path
import httpx
from streamlit.testing.v1 import AppTest
from chess4f.storage import Lake

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project / "apps"))
response = httpx.get("http://127.0.0.1:8000/openings/cube", params={"source": "lichess"}, timeout=180)
response.raise_for_status()
payload = response.json()
with Lake(project / "data").connection() as con:
    expected = con.execute("SELECT count(*) FROM silver_games WHERE source='lichess' AND rated AND speed='blitz' AND opening_family IS NOT NULL").fetchone()[0]
assert sum(row["n_games"] for row in payload["rows"]) == expected
assert all(row["white_wins"] + row["draws"] + row["black_wins"] == row["n_games"] for row in payload["rows"])
app = AppTest.from_file(str(project / "apps/dashboard.py"))
app.run(timeout=180)
app.sidebar.radio[0].set_value("Khai cuộc C1–C7").run(timeout=180)
assert not app.exception and not app.error
selector = next(item for item in app.selectbox if item.label == "Câu hỏi phân tích")
options = selector.options
for option in options:
    next(item for item in app.selectbox if item.label == "Câu hỏi phân tích").set_value(option).run(timeout=180)
    assert not app.exception and not app.error, option
    print("PASSED", option[:2])
app.multiselect[0].set_value([]).run(timeout=180)
assert not app.exception and app.warning
print("TRINO_CUBE_PARITY_AND_C1_C7_PASSED", expected)
