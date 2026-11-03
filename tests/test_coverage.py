from chess4f.coverage import last_day, ledger
from chess4f.pipeline import ingest_pgn
from conftest import pgn


def test_ledger_reports_month_and_boundary_days(lake_root, pgn_file):
    ingest_pgn(lake_root, pgn_file, "lichess")
    value = ledger(lake_root)
    assert value["kind"] == "observed_coverage_not_completeness_proof"
    source = value["sources"][0]
    assert source["source"] == "lichess"
    assert source["games"] == 2
    month = source["months"][0]
    assert month["month"] == "2026-09"
    assert month["games"] == 2
    assert month["days_with_games"] == 2
    assert month["first_day_games"] == 1
    assert month["last_day_games"] == 0
    assert month["boundary_risk"] == 1
    assert month["scan"]["limited"] is False


def test_ledger_counts_last_day_and_filters_source(lake_root, pgn_file):
    pgn_file.write_text(pgn_file.read_text() + pgn("MnOp3456", "2026.09.30"), encoding="utf-8")
    ingest_pgn(lake_root, pgn_file, "lichess")
    month = ledger(lake_root, "lichess")["sources"][0]["months"][0]
    assert month["last_day_games"] == 1
    assert month["boundary_risk"] == 2
    assert ledger(lake_root, "chesscom")["sources"] == []


def test_empty_lake_and_month_length(lake_root):
    assert ledger(lake_root)["sources"] == []
    assert last_day("2026-09") == "2026-09-30"
    assert last_day("2028-02") == "2028-02-29"
