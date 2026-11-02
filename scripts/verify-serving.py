"""Integration check: run from repository root after starting API and lakehouse."""
import json
import math
import os
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

api = os.getenv("CHESS4F_API", "http://127.0.0.1:8000")
results = []
with httpx.Client(timeout=180) as client:
    for source in ("lichess", "chesscom", "import"):
        outputs = {}
        for engine in ("duckdb", "trino"):
            response = client.get(f"{api}/overview", params={"source": source, "engine": engine})
            response.raise_for_status()
            outputs[engine] = response.json()
        local, remote = outputs["duckdb"], outputs["trino"]
        for field in ("games", "recognized", "opening_families"):
            assert local["summary"][field] == remote["summary"][field], (source, field)
        left = {row["opening_family"]: row for row in local["openings"]}
        right = {row["opening_family"]: row for row in remote["openings"]}
        assert left.keys() == right.keys(), source
        for family, row in left.items():
            for field, value in row.items():
                if field != "opening_family":
                    assert math.isclose(float(value), float(right[family][field]), abs_tol=1e-8), (source, family, field)
        if source == "lichess":
            expected_metrics = [f"{remote['summary'][field]:,}" for field in ("games", "recognized", "opening_families")]
        results.append({"source": source, "games": remote["summary"]["games"], "release": remote["release_id"], "parity": "passed"})

app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "apps/dashboard.py"))
app.run(timeout=180)
assert not app.exception and not app.error, "Initial dashboard failed"
app.selectbox[1].select("trino").run(timeout=180)
assert not app.exception and not app.error, "Trino dashboard failed"
assert [item.value for item in app.metric] == expected_metrics, "Dashboard metrics differ from API"
assert any("r_" in item.value for item in app.caption), "Missing release indicator"
print(json.dumps({"api": results, "streamlit_trino": "passed"}, indent=2))
