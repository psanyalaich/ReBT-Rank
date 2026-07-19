"""Unit tests for common.config (Task B3): deep-merge and typo rejection."""

from __future__ import annotations

from typing import Any

import pydantic

from rebt_rank.common.config import Config, _deep_merge


def _valid_config_dict() -> dict[str, Any]:
    return {
        "paths": {},
        "seeds": {"master": 1234},
        "data": {},
        "benchmark": {},
        "features": {"disabled_groups": []},
        "model": {"objective": "lambdarank", "num_leaves": 63},
        "calibration": {},
        "eval": {},
        "experiment": {"id": "main", "tags": ["headline"]},
    }


# --- _deep_merge -------------------------------------------------------------


def test_deep_merge_scalar_override() -> None:
    assert _deep_merge({"a": 1, "b": 2}, {"b": 3}) == {"a": 1, "b": 3}


def test_deep_merge_list_overrides_not_concatenates() -> None:
    assert _deep_merge({"a": [1, 2]}, {"a": [3]}) == {"a": [3]}


def test_deep_merge_mapping_recurses() -> None:
    base = {"m": {"x": 1, "y": 2}}
    overlay = {"m": {"y": 20, "z": 30}}
    assert _deep_merge(base, overlay) == {"m": {"x": 1, "y": 20, "z": 30}}


def test_deep_merge_does_not_mutate_inputs() -> None:
    base = {"m": {"x": 1}}
    overlay = {"m": {"y": 2}}
    _deep_merge(base, overlay)
    assert base == {"m": {"x": 1}}
    assert overlay == {"m": {"y": 2}}


# --- Config construction & typo rejection ------------------------------------


def test_config_constructs_from_valid_dict() -> None:
    cfg = Config(**_valid_config_dict())
    assert cfg.seeds.master == 1234
    assert cfg.model.num_leaves == 63
    assert cfg.model.objective == "lambdarank"
    assert cfg.experiment.tags == ["headline"]


def test_config_rejects_unknown_top_level_key() -> None:
    data = _valid_config_dict()
    data["typo_section"] = {}
    try:
        Config(**data)
    except pydantic.ValidationError:
        return
    raise AssertionError("unknown top-level key should be rejected")


def test_config_rejects_unknown_nested_key() -> None:
    data = _valid_config_dict()
    data["model"]["num_leavez"] = 10  # typo
    try:
        Config(**data)
    except pydantic.ValidationError:
        return
    raise AssertionError("unknown nested key should be rejected")


def test_empty_subconfig_rejects_extra_keys() -> None:
    data = _valid_config_dict()
    data["benchmark"]["unexpected"] = 1
    try:
        Config(**data)
    except pydantic.ValidationError:
        return
    raise AssertionError("empty sub-config should reject extra keys")


# --- immutability ------------------------------------------------------------


def test_config_is_frozen() -> None:
    cfg = Config(**_valid_config_dict())
    try:
        setattr(cfg, "seeds", cfg.seeds)
    except pydantic.ValidationError:
        return
    raise AssertionError("Config should be immutable (frozen)")


# --- hash --------------------------------------------------------------------


def test_config_hash_is_deterministic_and_hex() -> None:
    h1 = Config(**_valid_config_dict()).hash()
    h2 = Config(**_valid_config_dict()).hash()
    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 64  # sha256 hex digest


def test_config_hash_changes_with_content() -> None:
    cfg1 = Config(**_valid_config_dict())
    data = _valid_config_dict()
    data["model"]["num_leaves"] = 31
    cfg2 = Config(**data)
    assert cfg1.hash() != cfg2.hash()


# --- with_overlay ------------------------------------------------------------


def test_with_overlay_merges_and_revalidates() -> None:
    cfg = Config(**_valid_config_dict())
    new = cfg.with_overlay({"model": {"num_leaves": 31}})
    assert isinstance(new, Config)
    assert new.model.num_leaves == 31
    assert new.model.objective == "lambdarank"  # untouched by the overlay
    assert cfg.model.num_leaves == 63  # original unchanged (immutable)


def test_with_overlay_rejects_typo() -> None:
    cfg = Config(**_valid_config_dict())
    try:
        cfg.with_overlay({"model": {"num_leavez": 1}})
    except pydantic.ValidationError:
        return
    raise AssertionError("overlay introducing an unknown key should be rejected")
