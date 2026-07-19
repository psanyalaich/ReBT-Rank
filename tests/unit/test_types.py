"""Unit tests for common.types dataclasses (Task B2)."""

from __future__ import annotations

import dataclasses

from rebt_rank.common.types import MetricResult, RunManifest


def _make_manifest() -> RunManifest:
    return RunManifest(
        experiment_id="main-0a1b2c3d",
        git_sha="0" * 40,
        config_hash="deadbeef",
        snapshot_hashes={"rhea": "aaa", "brenda": "bbb"},
        seed=1234,
        created_at="2026-07-16T00:00:00+00:00",
        code_version="0.0.1",
    )


def _make_metric() -> MetricResult:
    return MetricResult(name="pr_auc", value=0.87, ci_lo=0.81, ci_hi=0.92, n=2000)


def test_run_manifest_construct() -> None:
    m = _make_manifest()
    assert m.experiment_id == "main-0a1b2c3d"
    assert m.snapshot_hashes["rhea"] == "aaa"
    assert m.seed == 1234
    assert m.code_version == "0.0.1"


def test_run_manifest_is_frozen() -> None:
    m = _make_manifest()
    try:
        setattr(m, "seed", 5)
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("RunManifest should be immutable (frozen)")


def test_run_manifest_to_dict_roundtrip() -> None:
    m = _make_manifest()
    d = m.to_dict()
    assert d["experiment_id"] == "main-0a1b2c3d"
    assert d["snapshot_hashes"] == {"rhea": "aaa", "brenda": "bbb"}
    assert d["seed"] == 1234
    assert RunManifest.from_dict(d) == m


def test_run_manifest_from_dict_ignores_extra_keys() -> None:
    m = _make_manifest()
    d = dict(m.to_dict())
    d["unexpected"] = "ignored"
    assert RunManifest.from_dict(d) == m


def test_metric_result_construct_and_roundtrip() -> None:
    r = _make_metric()
    assert r.name == "pr_auc"
    assert r.value == 0.87
    assert r.n == 2000
    d = r.to_dict()
    assert d == {
        "name": "pr_auc",
        "value": 0.87,
        "ci_lo": 0.81,
        "ci_hi": 0.92,
        "n": 2000,
    }
    assert MetricResult.from_dict(d) == r


def test_metric_result_is_frozen() -> None:
    r = _make_metric()
    try:
        setattr(r, "value", 0.0)
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("MetricResult should be immutable (frozen)")
