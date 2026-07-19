"""Unit tests for common.logging (Task B6).

Tests use only the public logging API (never structlog/rich) and request the
``tmp_path`` fixture by name, so no ``pytest`` import is needed (keeps the
type-check hook clean).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rebt_rank.common.logging import (
    Logger,
    ProgressReporter,
    bind_run_context,
    configure_logging,
    get_logger,
)


def _read_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_emits_start_and_end_events(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    configure_logging(log_file=p)
    with get_logger("m3_features").stage("build_features", k=20) as stage:
        stage.rows_in = 100
        stage.rows_out = 95
    events = _read_events(p)
    start, end = events[0], events[-1]
    assert start["event"] == "stage.start"
    assert start["stage"] == "build_features"
    assert start["module"] == "m3_features"
    assert start["k"] == 20
    assert end["event"] == "stage.end"
    assert end["rows_in"] == 100
    assert end["rows_out"] == 95
    assert "duration_s" in end


def test_stage_on_error_emits_error_and_reraises(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    configure_logging(log_file=p)
    raised = False
    try:
        with get_logger("m").stage("s"):
            raise ValueError("boom")
    except ValueError:
        raised = True
    assert raised
    events = _read_events(p)
    assert events[0]["event"] == "stage.start"
    assert events[-1]["event"] == "stage.error"
    assert "duration_s" in events[-1]


def test_every_record_has_core_fields(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    configure_logging(log_file=p)  # resets run context
    get_logger("m0_config").info("configured")
    event = _read_events(p)[-1]
    for key in ("timestamp", "level", "event", "module", "experiment_id"):
        assert key in event, f"missing core field: {key}"
    assert event["module"] == "m0_config"
    assert event["event"] == "configured"
    assert event["experiment_id"] == "unset"  # default until bind_run_context


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    configure_logging(log_file=p)
    configure_logging(log_file=p)  # second call must not duplicate anything
    get_logger("m").info("once")
    assert len(_read_events(p)) == 1


def test_bind_run_context_appears_on_events(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    configure_logging(log_file=p)
    bind_run_context(
        "exp-123", git_sha="abc123", config_hash="cfg456", code_version="0.0.1"
    )
    get_logger("m1_benchmark").info("built")
    event = _read_events(p)[-1]
    assert event["experiment_id"] == "exp-123"
    assert event["git_sha"] == "abc123"
    assert event["config_hash"] == "cfg456"
    assert event["code_version"] == "0.0.1"
    assert event["module"] == "m1_benchmark"


def test_logger_passes_primitive_fields_through(tmp_path: Path) -> None:
    # The layer logs only the primitive values the caller provides; it does not
    # inspect or special-case domain objects.
    p = tmp_path / "log.jsonl"
    configure_logging(log_file=p)
    get_logger("m").info("evt", count=3, names=["a", "b"], ok=True)
    event = _read_events(p)[-1]
    assert event["count"] == 3
    assert event["names"] == ["a", "b"]
    assert event["ok"] is True


def test_logger_public_methods(tmp_path: Path) -> None:
    public = {name for name in dir(Logger) if not name.startswith("_")}
    assert public == {"debug", "info", "warning", "error", "bind", "stage"}


def test_logger_levels_and_bind_propagate(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    configure_logging(log_file=p, level="DEBUG")
    log = get_logger("m").bind(context="ctx")
    log.debug("d")
    log.info("i")
    log.warning("w")
    log.error("e")
    events = _read_events(p)
    by_event = {ev["event"]: ev for ev in events}
    assert {"d", "i", "w", "e"} <= set(by_event)
    assert by_event["w"]["level"] == "warning"
    assert all(ev.get("context") == "ctx" for ev in events)  # bind propagated


def test_stage_context_is_narrow(tmp_path: Path) -> None:
    configure_logging(log_file=tmp_path / "log.jsonl")
    with get_logger("m").stage("s") as stage:
        stage.rows_in = 1
        stage.rows_out = 2
        extra_rejected = False
        try:
            setattr(stage, "extra", 3)  # slots forbids arbitrary attributes
        except AttributeError:
            extra_rejected = True
        assert extra_rejected


def test_progress_reporter_is_noop_passthrough() -> None:
    reporter = ProgressReporter(enabled=False)
    assert list(reporter.track([1, 2, 3])) == [1, 2, 3]
    with reporter.task(total=2) as task:
        task.advance()
        task.advance()  # must not raise


def test_progress_reporter_enabled_uses_rich() -> None:
    reporter = ProgressReporter(enabled=True)  # force the Rich code path
    assert list(reporter.track([1, 2, 3], description="t")) == [1, 2, 3]
    with reporter.task(total=3, description="t") as task:
        task.advance(2)
        task.advance(1)


def test_progress_auto_disables_under_json_and_non_tty(tmp_path: Path) -> None:
    # Default constructor consults the environment: JSON logging disables it...
    configure_logging(json_logs=True, log_file=tmp_path / "a.jsonl")
    assert list(ProgressReporter().track([1, 2])) == [1, 2]
    # ...and a non-TTY test env (no JSON logging) disables it too.
    configure_logging(json_logs=False, log_file=tmp_path / "b.jsonl")
    assert list(ProgressReporter().track([3, 4])) == [3, 4]
