"""Configuration module M0 (``rebt_rank.m0_config``).

Task M0a implements :func:`load_config`; M0b adds snapshot verification
(:func:`verify_snapshots` / :class:`SnapshotVerifier`); M0c adds RunManifest
build / persistence / identity checks (:func:`build_manifest`,
:func:`write_manifest`, :func:`load_manifest`, :func:`assert_manifest_matches`).
"""

from __future__ import annotations

from rebt_rank.m0_config.loader import load_config
from rebt_rank.m0_config.manifest import (
    assert_manifest_matches,
    build_manifest,
    load_manifest,
    write_manifest,
)
from rebt_rank.m0_config.snapshots import SnapshotVerifier, verify_snapshots

__all__ = [
    "load_config",
    "SnapshotVerifier",
    "verify_snapshots",
    "build_manifest",
    "write_manifest",
    "load_manifest",
    "assert_manifest_matches",
]
