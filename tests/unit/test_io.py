"""Unit tests for common.io (Task B4): atomic round-trip, sidecar, validation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from rebt_rank.common.io import (
    ArtifactWriter,
    read_json,
    read_parquet,
    write_json,
    write_parquet,
)
from rebt_rank.common.types import RunManifest


def _manifest() -> RunManifest:
    return RunManifest(
        experiment_id="test-0",
        git_sha="0" * 40,
        config_hash="abc",
        snapshot_hashes={},
        seed=0,
        created_at="2026-07-16T00:00:00+00:00",
        code_version="0.0.1",
    )


def _df() -> pd.DataFrame:
    return pd.DataFrame({"edge_id": ["a", "b"], "score": [0.1, 0.2]})


class _RecordingSchema:
    """Structural SupportsValidate: records call sizes, returns the frame."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        self.calls.append(len(df))
        return df


class _RaisingSchema:
    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        raise ValueError("schema rejected the frame")


# --- JSON --------------------------------------------------------------------


def test_json_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    obj = {"b": 2, "a": 1, "nested": {"y": [1, 2]}}
    assert write_json(obj, p) == p
    assert read_json(p) == obj


def test_json_is_deterministic_sorted_and_unicode(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    obj = {"b": 2, "a": 1, "delta": "ΔG"}
    write_json(obj, p)
    first = p.read_text(encoding="utf-8")
    write_json(obj, p)
    second = p.read_text(encoding="utf-8")
    assert first == second  # deterministic across writes
    assert first.index('"a"') < first.index('"b"')  # sort_keys
    assert "ΔG" in first  # ensure_ascii=False keeps non-ASCII literal
    assert "\n  " in first  # indent=2
    assert first == json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


# --- parquet round-trip + sidecar --------------------------------------------


def test_parquet_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "t.parquet"
    df = _df()
    assert write_parquet(df, p, manifest=_manifest()) == p
    assert p.exists()
    assert_frame_equal(read_parquet(p), df)


def test_write_parquet_writes_sidecar_manifest(tmp_path: Path) -> None:
    p = tmp_path / "t.parquet"
    m = _manifest()
    write_parquet(_df(), p, manifest=m)
    sidecar = p.with_name(p.name + ".manifest.json")
    assert sidecar.exists()
    assert read_json(sidecar) == m.to_dict()


def test_no_temp_files_remain_after_write(tmp_path: Path) -> None:
    write_parquet(_df(), tmp_path / "t.parquet", manifest=_manifest())
    leftovers = [x.name for x in tmp_path.iterdir() if ".tmp-" in x.name]
    assert leftovers == []


# --- schema validation is wired ----------------------------------------------


def test_schema_validate_called_on_write(tmp_path: Path) -> None:
    schema = _RecordingSchema()
    write_parquet(_df(), tmp_path / "t.parquet", manifest=_manifest(), schema=schema)
    assert schema.calls == [2]


def test_schema_validate_called_on_read(tmp_path: Path) -> None:
    p = tmp_path / "t.parquet"
    write_parquet(_df(), p, manifest=_manifest())
    schema = _RecordingSchema()
    read_parquet(p, schema=schema)
    assert schema.calls == [2]


# --- failure leaves nothing behind -------------------------------------------


def test_failed_validation_commits_nothing(tmp_path: Path) -> None:
    p = tmp_path / "t.parquet"
    try:
        write_parquet(_df(), p, manifest=_manifest(), schema=_RaisingSchema())
    except ValueError:
        pass
    assert not p.exists()
    assert not p.with_name(p.name + ".manifest.json").exists()
    assert list(tmp_path.iterdir()) == []  # no temp files either


# --- ArtifactWriter directly -------------------------------------------------


def test_artifact_writer_context_commits(tmp_path: Path) -> None:
    p = tmp_path / "t.parquet"
    with ArtifactWriter(p, _manifest()) as writer:
        writer.write_table(_df())
    assert p.exists()
    assert_frame_equal(read_parquet(p), _df())


def test_artifact_writer_body_error_commits_nothing(tmp_path: Path) -> None:
    p = tmp_path / "t.parquet"
    try:
        with ArtifactWriter(p, _manifest()) as writer:
            writer.write_table(_df())
            raise RuntimeError("boom in body")
    except RuntimeError:
        pass
    assert not p.exists()
    assert list(tmp_path.iterdir()) == []


def test_artifact_writer_commit_without_table_raises(tmp_path: Path) -> None:
    p = tmp_path / "t.parquet"
    try:
        with ArtifactWriter(p, _manifest()):
            pass  # never staged a table
    except ValueError:
        assert not p.exists()
        return
    raise AssertionError("committing without a written table should raise")
