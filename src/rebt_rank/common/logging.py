"""Structured logging and progress reporting for ReBT-Rank (Task B6).

A small, project-owned logging facade over ``structlog`` and ``rich``. **No other
module imports structlog or rich** -- downstream code depends only on the public
names below:

* :func:`configure_logging` -- one-time, idempotent setup (console + optional
  JSON-lines file); also resets bound run context.
* :func:`bind_run_context` -- bind run-wide immutable context (experiment_id,
  git_sha, config_hash, code_version) onto every subsequent event.
* :func:`get_logger` -- a :class:`Logger` bound to a module name.
* :class:`Logger` -- tiny wrapper exposing ``debug``/``info``/``warning``/
  ``error``/``bind`` plus :meth:`Logger.stage`, a context manager that emits a
  start event and an end event (with duration and optional row counts) around a
  pipeline stage.
* :class:`Timer` -- elapsed-time context manager.
* :class:`ProgressReporter` -- Rich progress, auto-no-op under JSON logging or a
  non-TTY.

Every emitted record always carries ``timestamp``, ``level``, ``event``,
``module``, and ``experiment_id`` (defaulting to ``"unset"`` until
:func:`bind_run_context` is called), plus any structured fields the caller adds.

Design invariant: this layer never inspects domain objects (DataFrames, Config,
RunManifest, dataclasses, ...). It only logs the primitive structured values a
caller explicitly passes, keeping the infrastructure generic and coupling-free.

TODO(B6): per-stage ``peak_mem`` (Part 10.1) and a ``log_exception`` helper
(Part 10.2) are intentionally deferred until a later milestone needs them --
reliable peak-memory measurement is platform-specific, and exception formatting
belongs at the application boundary.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TextIO, TypeVar

import structlog

__all__ = [
    "configure_logging",
    "bind_run_context",
    "get_logger",
    "Logger",
    "Timer",
    "ProgressReporter",
]

_T = TypeVar("_T")

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
_UNSET_EXPERIMENT_ID = "unset"

# Module-global state: the open JSON-lines file handle and whether JSON logging
# is active. Guarded so re-configuration never leaks handles or duplicates output.
_STATE: dict[str, Any] = {"log_fh": None, "json_logs": False}


# --- configuration -----------------------------------------------------------


class _JSONFileTee:
    """structlog processor: append each event as a JSON line to a file, then
    pass the event dict through unchanged to the console renderer."""

    __slots__ = ("_fh", "_render")

    def __init__(self, fh: TextIO) -> None:
        self._fh = fh
        self._render = structlog.processors.JSONRenderer(sort_keys=True)

    def __call__(self, logger: Any, method_name: str, event_dict: Any) -> Any:
        rendered = self._render(logger, method_name, dict(event_dict))
        if isinstance(rendered, bytes):
            rendered = rendered.decode("utf-8")
        self._fh.write(rendered + "\n")
        self._fh.flush()
        return event_dict


def _ensure_experiment_id(logger: Any, method_name: str, event_dict: Any) -> Any:
    """Guarantee every record carries an ``experiment_id`` (Part 10.2)."""
    event_dict.setdefault("experiment_id", _UNSET_EXPERIMENT_ID)
    return event_dict


def _close_log_file() -> None:
    fh = _STATE.get("log_fh")
    if fh is not None:
        try:
            fh.close()
        finally:
            _STATE["log_fh"] = None


def configure_logging(
    *,
    json_logs: bool = False,
    log_file: Path | None = None,
    level: str = "INFO",
) -> None:
    """Configure logging. Idempotent: safe to call repeatedly without
    duplicating handlers, processors, or emitted lines. Also resets any bound
    run context."""
    _close_log_file()
    structlog.contextvars.clear_contextvars()
    _STATE["json_logs"] = json_logs

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _ensure_experiment_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = path.open("w", encoding="utf-8")
        _STATE["log_fh"] = fh
        processors.append(_JSONFileTee(fh))
    processors.append(
        structlog.processors.JSONRenderer(sort_keys=True)
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_LEVELS[level]),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )


def bind_run_context(
    experiment_id: str,
    *,
    git_sha: str | None = None,
    config_hash: str | None = None,
    code_version: str | None = None,
) -> None:
    """Bind run-wide immutable context onto every subsequent log event.

    Restricted to run-scoped fields on purpose; module-specific values belong in
    individual log events, not bound globally.
    """
    context: dict[str, str] = {"experiment_id": experiment_id}
    if git_sha is not None:
        context["git_sha"] = git_sha
    if config_hash is not None:
        context["config_hash"] = config_hash
    if code_version is not None:
        context["code_version"] = code_version
    structlog.contextvars.bind_contextvars(**context)


# --- timing & stage context --------------------------------------------------


class Timer:
    """Context manager measuring elapsed wall-clock seconds."""

    __slots__ = ("_start", "_end")

    def __init__(self) -> None:
        self._start: float | None = None
        self._end: float | None = None

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        self._end = None
        return self

    def __exit__(self, *exc: object) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed(self) -> float:
        if self._start is None:
            return 0.0
        end = self._end if self._end is not None else time.perf_counter()
        return end - self._start


@dataclass(slots=True)
class StageContext:
    """Narrow, mutable handle for a stage's row counts (set inside ``Logger.stage``)."""

    rows_in: int | None = None
    rows_out: int | None = None


# --- logger ------------------------------------------------------------------


class Logger:
    """Tiny structured logger. The wrapped structlog logger is private; callers
    use only ``debug``/``info``/``warning``/``error``/``bind`` and ``stage``."""

    __slots__ = ("_logger",)

    def __init__(self, logger: Any) -> None:
        self._logger = logger

    def debug(self, event: str, **fields: Any) -> None:
        self._logger.debug(event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self._logger.info(event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._logger.warning(event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._logger.error(event, **fields)

    def bind(self, **fields: Any) -> Logger:
        return Logger(self._logger.bind(**fields))

    @contextmanager
    def stage(self, name: str, **params: Any) -> Iterator[StageContext]:
        """Emit ``stage.start`` on entry and ``stage.end`` (with duration and any
        row counts set on the yielded :class:`StageContext`) on exit. On error,
        emit ``stage.error`` with the duration and re-raise."""
        self.info("stage.start", stage=name, **params)
        ctx = StageContext()
        timer = Timer()
        try:
            with timer:
                yield ctx
        except BaseException:
            self.error("stage.error", stage=name, duration_s=timer.elapsed)
            raise
        self.info(
            "stage.end",
            stage=name,
            duration_s=timer.elapsed,
            rows_in=ctx.rows_in,
            rows_out=ctx.rows_out,
        )


def get_logger(module: str) -> Logger:
    """Return a :class:`Logger` that stamps ``module`` onto every event."""
    return Logger(structlog.get_logger().bind(module=module))


# --- progress ----------------------------------------------------------------


class _Task(Protocol):
    def advance(self, n: int = 1) -> None: ...


class _NoOpTask:
    def advance(self, n: int = 1) -> None:
        return None


class _RichTask:
    __slots__ = ("_progress", "_task_id")

    def __init__(self, progress: Any, task_id: Any) -> None:
        self._progress = progress
        self._task_id = task_id

    def advance(self, n: int = 1) -> None:
        self._progress.advance(self._task_id, n)


def _progress_enabled() -> bool:
    if _STATE.get("json_logs"):
        return False
    isatty = getattr(sys.stderr, "isatty", None)
    return bool(isatty()) if callable(isatty) else False


class ProgressReporter:
    """Rich progress reporting that becomes a transparent no-op when JSON logging
    is active or output is not a TTY (e.g. CI)."""

    __slots__ = ("_enabled",)

    def __init__(self, *, enabled: bool | None = None) -> None:
        self._enabled = _progress_enabled() if enabled is None else enabled

    def track(
        self,
        iterable: Iterable[_T],
        *,
        description: str = "working",
        total: int | None = None,
    ) -> Iterator[_T]:
        """Yield items from ``iterable``, showing a progress bar when enabled."""
        if not self._enabled:
            yield from iterable
            return
        from rich.progress import track as rich_track

        yield from rich_track(iterable, description=description, total=total)

    @contextmanager
    def task(
        self, *, description: str = "working", total: int | None = None
    ) -> Iterator[_Task]:
        """Yield a task handle with ``advance(n)``; a no-op handle when disabled."""
        if not self._enabled:
            yield _NoOpTask()
            return
        from rich.progress import Progress

        with Progress(transient=True) as progress:
            task_id = progress.add_task(description, total=total)
            yield _RichTask(progress, task_id)
