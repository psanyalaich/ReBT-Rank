"""RunManifest construction, persistence, and identity checks (Task M0c).

Keeps :class:`~rebt_rank.common.types.RunManifest` a pure, immutable value object
(B2): all build / serialize / load / validate logic lives here as functions --
the Engineering Design Part 3.1 methods, realized in the ``m0_config`` layer per
the approved architecture. Reuses existing substrate only and duplicates none of
it: :meth:`Config.hash` (B3), :func:`rebt_rank.common.provenance.git_sha` (B7),
the deterministic JSON of :mod:`rebt_rank.common.io` (B4), and
:meth:`RunManifest.to_dict` / :meth:`RunManifest.from_dict` (B2).

Scope (M0c): manifest build / write / load / identity assertion only. Snapshot
paths and the ``runs/<experiment_id>/`` location stay opaque; ROOT-relative path
resolution belongs to the later paths milestone (Part 5.2). Writing the
``resolved.yaml`` companion (Part 5.4) is orchestrator scope (J1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from rebt_rank import __version__
from rebt_rank.common.config import Config
from rebt_rank.common.errors import ConfigError
from rebt_rank.common.io import read_json, write_json
from rebt_rank.common.logging import get_logger
from rebt_rank.common.provenance import git_sha
from rebt_rank.common.types import RunManifest

__all__ = [
    "build_manifest",
    "write_manifest",
    "load_manifest",
    "assert_manifest_matches",
]

_logger = get_logger(__name__)

# Identity-defining fields compared by assert_manifest_matches (Part 5.4 / 10.1).
# created_at is provenance metadata and is intentionally excluded.
_IDENTITY_FIELDS = (
    "experiment_id",
    "git_sha",
    "config_hash",
    "snapshot_hashes",
    "seed",
    "code_version",
)


def build_manifest(config: Config) -> RunManifest:
    """Build a :class:`RunManifest` from ``config`` (Part 4.2 / 5.4).

    Pure construction: captures the current git SHA and a UTC timestamp but does
    no filesystem I/O and recomputes no hashes. ``experiment_id`` is
    ``f"{experiment.id}-{config_hash[:8]}"`` (Part 5.4); ``snapshot_hashes`` are
    copied from the pinned ``config.data.snapshots`` checksums (verifying them
    against disk is verify_snapshots' responsibility).
    """
    config_hash = config.hash()
    experiment_id = f"{config.experiment.id}-{config_hash[:8]}"
    snapshot_hashes = {
        name: snap.sha256 for name, snap in config.data.snapshots.items()
    }
    return RunManifest(
        experiment_id=experiment_id,
        git_sha=git_sha(),
        config_hash=config_hash,
        snapshot_hashes=snapshot_hashes,
        seed=config.seeds.master,
        created_at=datetime.now(UTC).isoformat(),
        code_version=__version__,
    )


def write_manifest(manifest: RunManifest, path: Path) -> Path:
    """Write ``manifest`` to ``path`` as deterministic JSON; return ``path``.

    ``path`` is opaque here; ``runs/<experiment_id>/manifest.json`` resolution
    belongs to the paths milestone.
    """
    write_json(manifest.to_dict(), path)
    _logger.info(
        "manifest.written", path=str(path), experiment_id=manifest.experiment_id
    )
    return path


def load_manifest(path: Path) -> RunManifest:
    """Load a :class:`RunManifest` previously written by :func:`write_manifest`."""
    return RunManifest.from_dict(read_json(path))


def assert_manifest_matches(expected: RunManifest, actual: RunManifest) -> None:
    """Assert two manifests share the same run identity (Part 7.5 reproduction).

    Compares only the identity-defining fields; ``created_at`` is excluded. On
    any difference, raises :class:`ConfigError` naming each differing field with
    both the expected and actual values.
    """
    diffs = []
    for field in _IDENTITY_FIELDS:
        expected_value = getattr(expected, field)
        actual_value = getattr(actual, field)
        if expected_value != actual_value:
            diffs.append(f"{field}: expected {expected_value!r}, got {actual_value!r}")
    if diffs:
        raise ConfigError("RunManifest mismatch: " + "; ".join(diffs))
