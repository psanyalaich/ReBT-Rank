"""Configuration models and deep-merge for ReBT-Rank (Task B3).

Immutable pydantic models for the run configuration (root :class:`Config` plus
the nine sub-configs of Engineering Design Part 3.1), a pure :func:`_deep_merge`
for layered config dicts (Part 5.1 semantics), and :meth:`Config.hash` /
:meth:`Config.with_overlay`.

Scope (agreed for B3): this module owns the pure models, ``_deep_merge``,
``Config.hash``, and ``Config.with_overlay`` only. It performs **no** file or
YAML I/O; reading YAML, resolving ``extends`` overlays, and ``load_config``
belong to M0a.

Sub-config models contain **only** the fields given as concrete assignments in
the frozen Engineering Design (the ``main.yaml`` / ablation examples in Part
5.1). Sub-configs without such a specification are genuine empty models
(``extra='forbid'``); their producing module extends them when their schema is
specified. Unknown keys are always rejected (typo protection, Part 5.1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Config",
    "PathsConfig",
    "SeedConfig",
    "SnapshotConfig",
    "DataConfig",
    "BenchmarkConfig",
    "FeatureConfig",
    "ModelConfig",
    "CalibrationConfig",
    "EvalConfig",
    "ExperimentConfig",
]


def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-merge ``overlay`` onto ``base`` (Part 5.1 semantics).

    Mappings recurse; scalars and lists in ``overlay`` override the value in
    ``base``. Neither input is mutated.
    """
    merged: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


class _StrictModel(BaseModel):
    """Base model for every config: immutable and typo-rejecting."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class PathsConfig(_StrictModel):
    """Filesystem paths (Part 5.2). Fields added by M0a when specified."""


class SeedConfig(_StrictModel):
    """Random-seed configuration (Part 5.3)."""

    master: int


class SnapshotConfig(_StrictModel):
    """A single pinned data snapshot: its version, checksum, and location.

    ``path`` is treated as an opaque location by M0b (``verify_snapshots``);
    ROOT-relative resolution belongs to the later paths milestone (Part 5.2).
    """

    version: str
    sha256: str
    path: str


class DataConfig(_StrictModel):
    """Dataset snapshot configuration (Part 5.1 ``data.yaml``).

    Maps a source name (e.g. ``rhea``, ``brenda``, ``uniprot``) to its pinned
    :class:`SnapshotConfig`. Empty by default; populated by ``data.yaml`` and
    checked by ``m0_config.verify_snapshots`` (M0b).
    """

    snapshots: dict[str, SnapshotConfig] = Field(default_factory=dict)


class BenchmarkConfig(_StrictModel):
    """Benchmark-construction configuration. Fields added by M1 when specified."""


class FeatureConfig(_StrictModel):
    """Feature-store configuration (Part 5.1 ablation example)."""

    disabled_groups: list[str]


class ModelConfig(_StrictModel):
    """Ranker/classifier configuration (Part 5.1 main.yaml example)."""

    objective: str
    num_leaves: int


class CalibrationConfig(_StrictModel):
    """Calibration / FDR configuration. Fields added by M5 when specified."""


class EvalConfig(_StrictModel):
    """Evaluation configuration. Fields added by M6 when specified."""


class ExperimentConfig(_StrictModel):
    """Experiment identity (Part 5.1 main.yaml example)."""

    id: str
    tags: list[str]


class Config(_StrictModel):
    """Root run configuration (Engineering Design Part 3.1)."""

    paths: PathsConfig
    seeds: SeedConfig
    data: DataConfig
    benchmark: BenchmarkConfig
    features: FeatureConfig
    model: ModelConfig
    calibration: CalibrationConfig
    eval: EvalConfig
    experiment: ExperimentConfig

    def hash(self) -> str:
        """Return a stable content hash (sha256 hex) of this configuration."""
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def with_overlay(self, overlay: Mapping[str, Any]) -> Self:
        """Return a new config with ``overlay`` deep-merged in and re-validated."""
        merged = _deep_merge(self.model_dump(), overlay)
        return type(self)(**merged)
