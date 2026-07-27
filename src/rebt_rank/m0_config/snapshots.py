"""DB snapshot checksum verification for ReBT-Rank (Task M0b).

Implements :func:`verify_snapshots` (Engineering Design Part 4.2) and the
:class:`SnapshotVerifier` helper (Part 1 / 3.9): recompute each pinned data
snapshot's SHA-256 via :func:`rebt_rank.common.provenance.hash_file` and compare
it to the checksum recorded in ``config.data.snapshots``. Any mismatch -- a
missing snapshot file or a differing digest -- raises
:class:`~rebt_rank.common.errors.SnapshotMismatchError` (fail fast, fail loud).

Scope (M0b): verification only. Snapshot paths are treated as opaque; ``REBT_ROOT``
/ ``PathsConfig`` resolution belongs to the later paths milestone (Part 5.2).
"""

from __future__ import annotations

from pathlib import Path

from rebt_rank.common.config import Config, SnapshotConfig
from rebt_rank.common.errors import SnapshotMismatchError
from rebt_rank.common.logging import get_logger
from rebt_rank.common.provenance import hash_file

__all__ = ["SnapshotVerifier", "verify_snapshots"]

_logger = get_logger(__name__)


class SnapshotVerifier:
    """Verify pinned data-snapshot checksums against files on disk."""

    def __init__(self, snapshots: dict[str, SnapshotConfig]) -> None:
        self._snapshots = snapshots

    def verify(self) -> None:
        """Check every snapshot's SHA-256, raising on the first violation.

        Raises :class:`SnapshotMismatchError` when a snapshot file is missing or
        its digest does not match the pinned ``sha256``.
        """
        for name, snapshot in self._snapshots.items():
            self._verify_one(name, snapshot)

    def _verify_one(self, name: str, snapshot: SnapshotConfig) -> None:
        path = Path(snapshot.path)
        if not path.is_file():
            raise SnapshotMismatchError(f"Snapshot '{name}' file not found: {path}")
        actual = hash_file(path)
        if actual != snapshot.sha256:
            raise SnapshotMismatchError(
                f"Snapshot '{name}' checksum mismatch at {path}: "
                f"expected {snapshot.sha256}, got {actual}"
            )


def verify_snapshots(config: Config) -> None:
    """Verify every pinned data snapshot in ``config`` (Part 4.2).

    A no-op when no snapshots are configured. Raises
    :class:`SnapshotMismatchError` on the first missing file or checksum
    mismatch.
    """
    snapshots = config.data.snapshots
    _logger.info("snapshots.verify.start", count=len(snapshots))
    SnapshotVerifier(snapshots).verify()
    _logger.info("snapshots.verify.ok", count=len(snapshots))
