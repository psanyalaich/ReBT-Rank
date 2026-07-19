"""Unit tests for common.provenance (Task B7)."""

from __future__ import annotations

import hashlib
import os
import random
import subprocess
from pathlib import Path
from unittest.mock import patch

import numpy as np

from rebt_rank.common.provenance import git_sha, hash_file, seed_everything

_HEX = set("0123456789abcdef")


# --- hash_file ---------------------------------------------------------------


def test_hash_file_matches_hashlib(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    content = b"hello world" * 1000
    p.write_bytes(content)
    assert hash_file(p) == hashlib.sha256(content).hexdigest()


def test_hash_file_is_chunk_size_invariant(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    p.write_bytes(bytes(range(256)) * 500)
    assert hash_file(p, chunk_size=7) == hash_file(p, chunk_size=1 << 20)


def test_hash_file_is_deterministic(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    p.write_bytes(b"abc")
    assert hash_file(p) == hash_file(p)


# --- git_sha -----------------------------------------------------------------


def test_git_sha_is_hex_or_unknown() -> None:
    sha = git_sha()
    assert sha == "unknown" or (len(sha) == 40 and set(sha) <= _HEX)
    short = git_sha(short=True)
    assert short == "unknown" or (7 <= len(short) <= 40 and set(short) <= _HEX)


def test_git_sha_returns_unknown_when_git_missing() -> None:
    with patch(
        "rebt_rank.common.provenance.subprocess.run", side_effect=FileNotFoundError
    ):
        assert git_sha() == "unknown"


def test_git_sha_returns_unknown_on_nonzero_exit() -> None:
    err = subprocess.CalledProcessError(128, ["git"])
    with patch("rebt_rank.common.provenance.subprocess.run", side_effect=err):
        assert git_sha() == "unknown"


# --- seed_everything ---------------------------------------------------------


def test_seed_everything_is_deterministic() -> None:
    seed_everything(42)
    first_py = [random.random() for _ in range(3)]
    first_np = np.random.rand(3).tolist()
    seed_everything(42)
    second_py = [random.random() for _ in range(3)]
    second_np = np.random.rand(3).tolist()
    assert first_py == second_py
    assert first_np == second_np


def test_seed_everything_sets_pythonhashseed() -> None:
    seed_everything(123)
    assert os.environ["PYTHONHASHSEED"] == "123"


def test_different_seeds_differ() -> None:
    seed_everything(1)
    a = np.random.rand(3).tolist()
    seed_everything(2)
    b = np.random.rand(3).tolist()
    assert a != b
