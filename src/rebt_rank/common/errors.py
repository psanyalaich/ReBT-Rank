"""Typed exception hierarchy for ReBT-Rank (Task B1).

Every error raised by the package derives from :class:`RebtRankError`, so a
caller can catch the whole family with a single ``except RebtRankError``. The
concrete subclasses mirror the failure modes named in the Engineering Design
(Part 4.1); each docstring records the module that raises it.

Structured error *reporting* (offending artifact path, failing field,
remediation hint) is a concern of the logging layer (Task B6) and is
intentionally not modelled on these exception types yet.
"""

from __future__ import annotations

__all__ = [
    "RebtRankError",
    "ConfigError",
    "SnapshotMismatchError",
    "SchemaValidationError",
    "LeakageError",
    "DataCoverageError",
    "ModelTrainingError",
    "CalibrationError",
    "ReportingError",
]


class RebtRankError(Exception):
    """Base class for every error raised by ReBT-Rank."""


class ConfigError(RebtRankError):
    """Configuration is invalid, missing, unmergeable, or has unknown keys (M0)."""


class SnapshotMismatchError(RebtRankError):
    """A database snapshot checksum does not match the pinned value (M0)."""


class SchemaValidationError(RebtRankError):
    """An on-disk table failed its schema contract (common.io / all modules)."""


class LeakageError(RebtRankError):
    """A benchmark split leakage invariant was violated (M1)."""


class DataCoverageError(RebtRankError):
    """Required data coverage fell below its threshold, e.g. ΔG availability (M3)."""


class ModelTrainingError(RebtRankError):
    """Model training failed or produced an invalid artifact (M4)."""


class CalibrationError(RebtRankError):
    """Calibration, conformal prediction, or FDR estimation failed (M5)."""


class ReportingError(RebtRankError):
    """Ranked-output, report-card, or figure generation failed (M7)."""
