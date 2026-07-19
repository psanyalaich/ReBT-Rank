"""Provenance and reproducibility helpers for ReBT-Rank (Task B7).

Public API:

* :func:`hash_file` -- chunked SHA-256 of a file's contents (snapshot/input
  checksums for the run manifest and M0 snapshot verification).
* :func:`git_sha` -- the current commit SHA via the ``git`` CLI; the sentinel
  ``"unknown"`` when git or a repository is unavailable (e.g. a slim container).
* :func:`seed_everything` -- deterministically and idempotently seed the Python
  and NumPy RNGs, and set ``PYTHONHASHSEED`` for child processes.

Deferred by design: a component-seed derivation helper (Part 5.3) is added when a
component first needs it; LightGBM seeding is applied per-model in M4 (its
determinism is a model parameter, not a global call).
"""

from __future__ import annotations

import hashlib
import os
import random
import subprocess
from pathlib import Path

import numpy as np

__all__ = ["hash_file", "git_sha", "seed_everything"]

_CHUNK_SIZE = 1 << 20  # 1 MiB
_GIT_UNAVAILABLE = "unknown"


def hash_file(path: Path, *, chunk_size: int = _CHUNK_SIZE) -> str:
    """Return the SHA-256 hex digest of the file at ``path``, read in chunks so
    arbitrarily large snapshots hash in bounded memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_sha(*, short: bool = False) -> str:
    """Return the current git commit SHA, or ``"unknown"`` when git or a
    repository is unavailable. ``short`` returns the abbreviated SHA."""
    args = ["git", "rev-parse"]
    if short:
        args.append("--short")
    args.append("HEAD")
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return _GIT_UNAVAILABLE
    return result.stdout.strip() or _GIT_UNAVAILABLE


def seed_everything(seed: int) -> None:
    """Deterministically and idempotently seed the Python and NumPy RNGs.

    Calling this twice with the same ``seed`` restores the same RNG state.
    ``PYTHONHASHSEED`` is set so that *child* processes inherit a deterministic
    hash seed; it does not change the already-started interpreter's hashing.
    LightGBM seeding is applied per-model in M4.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
