"""Unit tests for the typed exception hierarchy (Task B1).

Tests use plain ``try/except`` rather than ``pytest.raises`` so the module has
no third-party imports and stays clean under the type-check hook.
"""

from __future__ import annotations

from rebt_rank.common.errors import (
    CalibrationError,
    ConfigError,
    DataCoverageError,
    LeakageError,
    ModelTrainingError,
    RebtRankError,
    ReportingError,
    SchemaValidationError,
    SnapshotMismatchError,
)

_CONCRETE_ERRORS = (
    ConfigError,
    SnapshotMismatchError,
    SchemaValidationError,
    LeakageError,
    DataCoverageError,
    ModelTrainingError,
    CalibrationError,
    ReportingError,
)


def test_base_is_exception() -> None:
    assert issubclass(RebtRankError, Exception)


def test_all_concrete_errors_derive_from_base() -> None:
    for err in _CONCRETE_ERRORS:
        assert issubclass(err, RebtRankError)


def test_hierarchy_has_expected_membership() -> None:
    # Exactly the eight concrete errors from Engineering Design Part 4.1.
    assert len(_CONCRETE_ERRORS) == 8
    assert len(set(_CONCRETE_ERRORS)) == 8


def test_each_error_can_be_raised_and_caught_as_base() -> None:
    for err in _CONCRETE_ERRORS:
        try:
            raise err("boom")
        except RebtRankError as exc:
            assert isinstance(exc, err)
            assert str(exc) == "boom"
        else:  # pragma: no cover - defensive; the raise above always fires
            raise AssertionError(f"{err.__name__} was not raised")


def test_catching_specific_error_does_not_catch_a_sibling() -> None:
    try:
        raise ConfigError("cfg")
    except LeakageError:  # pragma: no cover - must never match a ConfigError
        raise AssertionError("ConfigError was caught as LeakageError")
    except ConfigError as exc:
        assert str(exc) == "cfg"
