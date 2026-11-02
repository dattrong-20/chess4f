import pytest
dg = pytest.importorskip("dagster")
from chess4f import definitions as orchestration


def test_jobs_and_schedules_load():
    dg.Definitions.validate_loadable(orchestration.defs)
    assert orchestration.refresh_schedule.execution_timezone == "Asia/Barnaul"
    assert orchestration.refresh_schedule.cron_schedule == "0 8 * * 0"


def test_unavailable_source_never_builds_or_publishes(monkeypatch):
    monkeypatch.setattr(orchestration, "refresh_months", lambda *a, **k: [{"status": "not_yet_available"}])
    monkeypatch.setattr(orchestration.lakehouse, "snapshot", lambda *a: pytest.fail("Must not snapshot unavailable source"))
    result = orchestration.monthly_refresh_job.execute_in_process()
    assert result.success
    assert result.output_for_node("publish_release") == {"status": "unchanged"}


def test_scheduled_scope_is_bounded():
    with pytest.raises(ValueError, match="limit"):
        orchestration.collect_source(dg.build_op_context(), orchestration.RefreshConfig(limit=5001))
