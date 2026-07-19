"""Core data types for ReBT-Rank (Task B2).

Frozen dataclasses plus in-memory serialization (``to_dict`` / ``from_dict``).
Only the dataclasses whose fields are fixed by the frozen design are defined
here:

* :class:`RunManifest` - fields per Engineering Design Part 3.1.
* :class:`MetricResult` - fields per Engineering Design Part 6.2 (metrics.json).

Out of scope for B2 (by design):

* Persistence (``write`` / ``load``), ``from_config``, and ``assert_matches``
  live in M0c; they depend on the provenance helpers introduced in Task B7.
* ``TrainResult`` and ``AuditReport`` are intentionally NOT defined here. Their
  fields are unspecified in the frozen design, so they are left to their
  producing modules (M4 and M1) to avoid introducing unfrozen shared interfaces.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Any, Self

__all__ = ["RunManifest", "MetricResult"]


@dataclass(frozen=True)
class RunManifest:
    """Provenance record binding a run to its code, data, and seed (Part 3.1).

    This class models the data and its in-memory serialization only. Field
    *values* (git SHA, config hash, timestamp, ...) are populated by
    ``RunManifest.from_config`` in M0c.
    """

    experiment_id: str
    git_sha: str
    config_hash: str
    snapshot_hashes: dict[str, str]
    seed: int
    created_at: str
    code_version: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable copy of this manifest."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a manifest from a mapping produced by :meth:`to_dict`.

        Only the declared fields are read; any extra keys are ignored.
        """
        return cls(**{f.name: data[f.name] for f in fields(cls)})


@dataclass(frozen=True)
class MetricResult:
    """A single evaluation metric with its bootstrap CI and support (Part 6.2)."""

    name: str
    value: float
    ci_lo: float
    ci_hi: float
    n: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable copy of this metric result."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a metric result from a mapping produced by :meth:`to_dict`.

        Only the declared fields are read; any extra keys are ignored.
        """
        return cls(**{f.name: data[f.name] for f in fields(cls)})
