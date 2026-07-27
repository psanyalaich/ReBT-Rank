"""Unit tests for ``rebt_rank.m0_config.load_config`` (Task M0a).

Tests avoid importing ``pytest`` (the mypy pre-commit hook has no pytest): they
use the bare ``tmp_path`` fixture parameter, ``try/except`` for expected errors,
and ``unittest.mock`` for the logging assertion.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest import mock

from rebt_rank.common.config import Config
from rebt_rank.common.errors import ConfigError, SnapshotMismatchError
from rebt_rank.common.provenance import hash_file
from rebt_rank.m0_config import (
    assert_manifest_matches,
    build_manifest,
    load_config,
    load_manifest,
    verify_snapshots,
    write_manifest,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

_BASE = """
paths: {}
seeds:
  master: 7
data: {}
benchmark: {}
features:
  disabled_groups: []
model:
  objective: lambdarank
  num_leaves: 31
calibration: {}
eval: {}
experiment:
  id: base
  tags: []
"""

_MAIN = """
extends: [base, data]
experiment:
  id: main
  tags: [headline]
model:
  num_leaves: 63
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _make_tree(root: Path) -> Path:
    """Build a minimal ``configs`` tree and return the main experiment path."""
    configs = root / "configs"
    _write(configs / "base.yaml", _BASE)
    _write(configs / "data.yaml", "data: {}\n")
    return _write(configs / "experiments" / "main.yaml", _MAIN)


def test_resolves_repo_main_yaml_to_config() -> None:
    """The shipped configs/experiments/main.yaml resolves to a valid Config."""
    config = load_config(_REPO_ROOT / "configs" / "experiments" / "main.yaml")
    assert isinstance(config, Config)
    assert config.experiment.id == "main"
    assert config.experiment.tags == ["headline"]
    assert config.model.objective == "lambdarank"
    assert config.model.num_leaves == 63
    assert config.features.disabled_groups == []
    assert config.seeds.master == 42


def test_extends_merges_deepest_last(tmp_path: Path) -> None:
    """The experiment file's keys override its base parents."""
    main = _make_tree(tmp_path)
    config = load_config(main)
    # main overrides base's model.num_leaves (31 -> 63) and experiment identity.
    assert config.model.num_leaves == 63
    assert config.model.objective == "lambdarank"  # inherited from base
    assert config.experiment.id == "main"
    assert config.seeds.master == 7  # inherited from base


def test_overlay_applied_last(tmp_path: Path) -> None:
    """An overlay name is merged on top of the resolved config."""
    main = _make_tree(tmp_path)
    _write(tmp_path / "configs" / "over.yaml", "model:\n  num_leaves: 127\n")
    config = load_config(main, overlay="over")
    assert config.model.num_leaves == 127


def test_extends_accepts_single_string(tmp_path: Path) -> None:
    """A scalar ``extends`` is treated as a one-element list."""
    _write(tmp_path / "configs" / "base.yaml", _BASE)
    child = _write(
        tmp_path / "configs" / "child.yaml",
        "extends: base\nmodel:\n  num_leaves: 99\n",
    )
    config = load_config(child)
    assert config.model.num_leaves == 99
    assert config.experiment.id == "base"


def test_extends_resolves_without_configs_dir(tmp_path: Path) -> None:
    """When no ancestor ``configs`` dir exists, names resolve beside the file."""
    _write(tmp_path / "base.yaml", _BASE)
    child = _write(
        tmp_path / "child.yaml", "extends: [base]\nmodel:\n  num_leaves: 5\n"
    )
    config = load_config(child)
    assert config.model.num_leaves == 5
    assert config.experiment.id == "base"


def test_unknown_key_raises_config_error(tmp_path: Path) -> None:
    """An unknown key is rejected (typo protection, Part 5.1)."""
    _write(tmp_path / "configs" / "base.yaml", _BASE)
    bad = _write(
        tmp_path / "configs" / "bad.yaml",
        "extends: base\nnot_a_real_section: {}\n",
    )
    try:
        load_config(bad)
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError for unknown key")


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    try:
        load_config(tmp_path / "configs" / "nope.yaml")
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError for missing file")


def test_missing_extends_target_raises_config_error(tmp_path: Path) -> None:
    child = _write(tmp_path / "configs" / "child.yaml", "extends: [ghost]\n")
    try:
        load_config(child)
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError for missing extends target")


def test_circular_extends_raises_config_error(tmp_path: Path) -> None:
    _write(tmp_path / "configs" / "a.yaml", "extends: [b]\n")
    b = _write(tmp_path / "configs" / "b.yaml", "extends: [a]\n")
    try:
        load_config(b)
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError for circular extends")


def test_non_mapping_top_level_raises_config_error(tmp_path: Path) -> None:
    bad = _write(tmp_path / "configs" / "list.yaml", "- one\n- two\n")
    try:
        load_config(bad)
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError for non-mapping top level")


def test_unparseable_scalar_raises_config_error(tmp_path: Path) -> None:
    bad = _write(tmp_path / "configs" / "scalar.yaml", "42\n")
    try:
        load_config(bad)
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError for scalar top level")


def test_bad_extends_type_raises_config_error(tmp_path: Path) -> None:
    bad = _write(tmp_path / "configs" / "bad.yaml", "extends: 5\n")
    try:
        load_config(bad)
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError for non-string extends")


def test_logs_resolved_hash(tmp_path: Path) -> None:
    """load_config logs the resolved config hash (Part 4.2)."""
    main = _make_tree(tmp_path)
    with mock.patch("rebt_rank.m0_config.loader._logger") as logger:
        config = load_config(main)
    logger.info.assert_called_once()
    _, kwargs = logger.info.call_args
    assert kwargs["config_hash"] == config.hash()


# --- verify_snapshots (M0b) --------------------------------------------------


def _config_with_snapshots(snapshots: dict[str, dict[str, str]]) -> Config:
    # Build via a dict[str, Any] and unpack (mypy-safe: pydantic is
    # dataclass_transform, so passing dict literals as the typed model kwargs
    # would fail type-checking). Matches the idiom in test_config.py.
    data: dict[str, Any] = {
        "paths": {},
        "seeds": {"master": 1},
        "data": {"snapshots": snapshots},
        "benchmark": {},
        "features": {"disabled_groups": []},
        "model": {"objective": "lambdarank", "num_leaves": 63},
        "calibration": {},
        "eval": {},
        "experiment": {"id": "t", "tags": []},
    }
    return Config(**data)


def test_verify_snapshots_noop_when_empty() -> None:
    """No configured snapshots -> verification is a no-op."""
    verify_snapshots(_config_with_snapshots({}))


def test_verify_snapshots_passes_on_matching_checksum(tmp_path: Path) -> None:
    snap = tmp_path / "rhea.tsv"
    snap.write_text("rhea snapshot", encoding="utf-8")
    cfg = _config_with_snapshots(
        {"rhea": {"version": "1", "sha256": hash_file(snap), "path": str(snap)}}
    )
    verify_snapshots(cfg)  # must not raise


def test_verify_snapshots_raises_on_wrong_checksum(tmp_path: Path) -> None:
    snap = tmp_path / "rhea.tsv"
    snap.write_text("rhea snapshot", encoding="utf-8")
    cfg = _config_with_snapshots(
        {"rhea": {"version": "1", "sha256": "deadbeef", "path": str(snap)}}
    )
    try:
        verify_snapshots(cfg)
    except SnapshotMismatchError:
        return
    raise AssertionError("expected SnapshotMismatchError on checksum mismatch")


def test_verify_snapshots_raises_on_missing_file(tmp_path: Path) -> None:
    cfg = _config_with_snapshots(
        {"rhea": {"version": "1", "sha256": "abc", "path": str(tmp_path / "gone")}}
    )
    try:
        verify_snapshots(cfg)
    except SnapshotMismatchError:
        return
    raise AssertionError("expected SnapshotMismatchError on missing file")


# --- manifest build / persistence / identity (M0c) ---------------------------


def test_build_manifest_fields() -> None:
    cfg = _config_with_snapshots(
        {"rhea": {"version": "1", "sha256": "abc", "path": "/x"}}
    )
    manifest = build_manifest(cfg)
    assert manifest.config_hash == cfg.hash()
    assert manifest.experiment_id == f"t-{cfg.hash()[:8]}"
    assert manifest.snapshot_hashes == {"rhea": "abc"}
    assert manifest.seed == 1
    assert manifest.code_version  # from rebt_rank.__version__, non-empty
    assert manifest.created_at.endswith("+00:00")  # UTC ISO-8601


def test_manifest_round_trip(tmp_path: Path) -> None:
    manifest = build_manifest(_config_with_snapshots({}))
    path = write_manifest(manifest, tmp_path / "manifest.json")
    loaded = load_manifest(path)
    assert loaded == manifest
    assert_manifest_matches(manifest, loaded)  # identical identity -> no raise


def test_assert_matches_ignores_created_at() -> None:
    manifest = build_manifest(_config_with_snapshots({}))
    other = replace(manifest, created_at="2000-01-01T00:00:00+00:00")
    assert_manifest_matches(manifest, other)  # differs only in created_at -> no raise


def test_assert_matches_raises_on_identity_diff() -> None:
    manifest = build_manifest(_config_with_snapshots({}))
    other = replace(manifest, config_hash="different-hash")
    try:
        assert_manifest_matches(manifest, other)
    except ConfigError as exc:
        assert "config_hash" in str(exc)
        assert "different-hash" in str(exc)
        return
    raise AssertionError("expected ConfigError on identity mismatch")
