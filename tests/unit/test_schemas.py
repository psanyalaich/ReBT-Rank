"""Unit tests for common.schemas (Task B5): validate/reject per table."""

from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from rebt_rank.common.errors import SchemaValidationError
from rebt_rank.common.schemas import (
    Calibrated,
    CandidateEdges,
    Features,
    LabeledEdges,
    Scores,
    TableSchema,
)

_ALL: tuple[TableSchema, ...] = (
    LabeledEdges,
    CandidateEdges,
    Features,
    Scores,
    Calibrated,
)


def _assert_rejects(schema: TableSchema, df: pd.DataFrame, why: str) -> None:
    try:
        schema.validate(df)
    except SchemaValidationError:
        return
    raise AssertionError(f"expected rejection: {why}")


# --- shared contract ---------------------------------------------------------


def test_every_example_validates_unchanged() -> None:
    for schema in _ALL:
        assert_frame_equal(schema.validate(schema.example()), schema.example())


def test_tableschema_exposes_only_validate_and_example() -> None:
    for schema in _ALL:
        public = {name for name in dir(schema) if not name.startswith("_")}
        assert public == {"validate", "example"}


def test_validation_error_is_project_type_not_pandera() -> None:
    df = LabeledEdges.example()
    df["label"] = pd.array([2, 0], dtype="int8")
    try:
        LabeledEdges.validate(df)
    except SchemaValidationError as exc:
        assert type(exc).__module__.startswith("rebt_rank")
        return
    raise AssertionError("expected SchemaValidationError")


# --- labeled_edges -----------------------------------------------------------


def test_labeled_edges_rejects_out_of_domain_label() -> None:
    df = LabeledEdges.example()
    df["label"] = pd.array([2, 0], dtype="int8")
    _assert_rejects(LabeledEdges, df, "label must be in {0, 1}")


def test_labeled_edges_rejects_unknown_source() -> None:
    df = LabeledEdges.example()
    df["source"] = pd.Categorical(["kegg", "brenda"])
    _assert_rejects(LabeledEdges, df, "source must be in {rhea, brenda}")


def test_labeled_edges_rejects_extra_column() -> None:
    df = LabeledEdges.example()
    df["extra"] = [1, 2]
    _assert_rejects(LabeledEdges, df, "strict schema rejects unknown columns")


# --- candidate_edges ---------------------------------------------------------


def test_candidate_edges_rejects_bad_ec() -> None:
    df = CandidateEdges.example()
    df["ec"] = ["not-an-ec", "2.7.1.-"]
    _assert_rejects(CandidateEdges, df, "ec must match the EC regex")


def test_candidate_edges_rejects_out_of_range_score() -> None:
    df = CandidateEdges.example()
    df["analog_score"] = pd.array([1.5, 0.4], dtype="float32")
    _assert_rejects(CandidateEdges, df, "analog_score must be in [0, 1]")


# --- features ----------------------------------------------------------------


def test_features_rejects_unknown_column() -> None:
    df = Features.example()
    df["junk"] = [1, 2]
    _assert_rejects(Features, df, "strict schema rejects unknown columns")


def test_features_rejects_missing_feature_column() -> None:
    df = Features.example().drop(columns=["f07"])
    _assert_rejects(Features, df, "all of f01..f15 are required")


# --- scores ------------------------------------------------------------------


def test_scores_rejects_non_finite_score() -> None:
    df = Scores.example()
    df["raw_score"] = pd.array([float("inf"), 0.1], dtype="float32")
    _assert_rejects(Scores, df, "raw_score must be finite")


def test_scores_rejects_duplicate_edge_model_fold() -> None:
    df = Scores.example()
    df["model"] = pd.Categorical(["ranker", "ranker"])
    _assert_rejects(Scores, df, "(edge_id, model, fold) must be unique")


# --- calibrated --------------------------------------------------------------


def test_calibrated_rejects_out_of_range_probability() -> None:
    df = Calibrated.example()
    df["p_true"] = pd.array([1.5, 0.2], dtype="float32")
    _assert_rejects(Calibrated, df, "p_true must be in [0, 1]")


def test_calibrated_rejects_non_list_conformal_set() -> None:
    df = Calibrated.example()
    df["conformal_set"] = ["g1", "g2"]  # strings, not lists
    _assert_rejects(Calibrated, df, "conformal_set entries must be lists")
