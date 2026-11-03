"""Observed coverage ledger: what was imported, never a completeness claim.

A monthly Lichess archive is scanned file by file. A game whose UTC date is
near a month boundary can live in the adjacent source file, so counting the
Silver rows proves what this dataset contains, not that a calendar month is
complete. The ledger reports those boundary days explicitly so the gap is
visible instead of being hidden in a total.
"""
import calendar
import json
from pathlib import Path

from .storage import Lake, utc_now

NOTES = [
    "Counts describe imported Silver rows only; they do not prove full source or calendar-month coverage.",
    "Boundary days are reported because UTC timestamps can spill into an adjacent monthly source file.",
    "A 'limited' checkpoint means collection stopped at a cap, not that the month was exhausted.",
]


def last_day(month):
    year, mon = (int(part) for part in month.split("-"))
    return f"{month}-{calendar.monthrange(year, mon)[1]:02d}"


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def checkpoints(root, source, month):
    """Return the collection checkpoints relevant to one source/month, if any."""
    folder = Path(root) / "metadata"
    result = {}
    if source == "lichess":
        refresh = _read_json(folder / "refresh" / f"{month}.json")
        if refresh:
            result["refresh"] = {key: refresh.get(key) for key in
                                 ("status", "committed_limit", "committed_at", "processor_version", "run_id")}
        backfill = _read_json(folder / "months" / f"{month}.json")
        if backfill:
            result["backfill"] = {key: backfill.get(key) for key in ("status", "limit", "run_id")}
    limited = any(item.get("status") == "limited" for item in result.values())
    return {"limited": limited, **result}


def ledger(root, source=None):
    """Summarize imported games per source/month/day with scan checkpoints."""
    lake = Lake(root)
    value = dict(generated_at=utc_now(), kind="observed_coverage_not_completeness_proof",
                 notes=list(NOTES), sources=[])
    if not lake.exists("silver/games"):
        return value
    where, parameters = (" WHERE source=?", [source]) if source else ("", [])
    with lake.connection() as con:
        rows = con.execute(f"""
            SELECT source, year_month, substr(played_at, 1, 10) game_day,
                   count(*)::BIGINT games,
                   count(opening_family)::BIGINT recognized,
                   sum(CASE WHEN avg_elo IS NULL THEN 1 ELSE 0 END)::BIGINT unknown_rating,
                   sum(CASE WHEN rated AND speed='blitz' THEN 1 ELSE 0 END)::BIGINT rated_blitz
            FROM silver_games{where}
            GROUP BY source, year_month, game_day ORDER BY source, year_month, game_day
        """, parameters).fetchall()
    by_source = {}
    for name, month, day, games, recognized, unknown, rated_blitz in rows:
        entry = by_source.setdefault(name, {"source": name, "months": {}, "first_game": day, "last_game": day})
        entry["first_game"] = min(entry["first_game"], day)
        entry["last_game"] = max(entry["last_game"], day)
        month_entry = entry["months"].setdefault(month, dict(
            month=month, games=0, recognized=0, unknown_rating=0, rated_blitz=0,
            days_with_games=0, first_day_games=0, last_day_games=0))
        month_entry["games"] += games
        month_entry["recognized"] += recognized
        month_entry["unknown_rating"] += unknown
        month_entry["rated_blitz"] += rated_blitz
        month_entry["days_with_games"] += 1
        if day == f"{month}-01":
            month_entry["first_day_games"] += games
        if day == last_day(month):
            month_entry["last_day_games"] += games
    for name in sorted(by_source):
        entry = by_source[name]
        months = []
        for month in sorted(entry["months"]):
            item = entry["months"][month]
            item["boundary_risk"] = item["first_day_games"] + item["last_day_games"]
            item["scan"] = checkpoints(root, name, month)
            months.append(item)
        value["sources"].append(dict(
            source=name, games=sum(m["games"] for m in months),
            recognized=sum(m["recognized"] for m in months),
            first_game=entry["first_game"], last_game=entry["last_game"], months=months))
    return value
