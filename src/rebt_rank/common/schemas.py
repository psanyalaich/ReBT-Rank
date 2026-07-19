"""Pandera table schemas for ReBT-Rank (Task B5).

One :class:`TableSchema` per on-disk table named in Engineering Design Part 3.1
(``LabeledEdges``, ``CandidateEdges``, ``Features``, ``Scores``, ``Calibrated``),
with columns and rules from Part 6.2. Each wraps a private Pandera
``DataFrameSchema`` (the pandas backend) and exposes **only** the frozen
interface: :meth:`~TableSchema.validate` and :meth:`~TableSchema.example`.

Pandera is kept entirely behind this abstraction: the rest of the codebase
interacts through the ``common.io.SupportsValidate`` protocol and never imports
Pandera. Validation failures are re-raised as the project's
:class:`~rebt_rank.common.errors.SchemaValidationError`, so Pandera exceptions
never leak past this module.

The ``Features`` schema validates structural shape only (``f01``..``f15`` plus
regex ``*_missing`` flags); feature semantics remain the responsibility of the
future ``FeatureRegistry`` (Task E1).
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaError, SchemaErrors

from rebt_rank.common.errors import SchemaValidationError

__all__ = [
    "TableSchema",
    "LabeledEdges",
    "CandidateEdges",
    "Features",
    "Scores",
    "Calibrated",
]

# EC number, allowing hierarchical relaxation (e.g. "1.1.1.1" or "1.1.-.-").
_EC_REGEX = r"^\d+\.(\d+|-)\.(\d+|-)\.(\d+|-)$"


def _finite(series: pd.Series) -> pd.Series:
    """Element-wise finiteness check (rejects +/-inf and NaN)."""
    return (series > float("-inf")) & (series < float("inf"))


class TableSchema:
    """A named on-disk table contract exposing only ``validate`` and ``example``.

    The wrapped Pandera schema is private; callers use this object through the
    ``SupportsValidate`` protocol (``validate(df) -> df``).
    """

    def __init__(
        self,
        name: str,
        schema: pa.DataFrameSchema,
        example: Callable[[], pd.DataFrame],
    ) -> None:
        self._name = name
        self._schema = schema
        self._example = example

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate ``df`` against the table contract.

        Returns the validated frame; raises
        :class:`~rebt_rank.common.errors.SchemaValidationError` on any violation.
        """
        try:
            return self._schema.validate(df)
        except (SchemaError, SchemaErrors) as exc:
            raise SchemaValidationError(f"{self._name}: {exc}") from exc

    def example(self) -> pd.DataFrame:
        """Return a small, deterministic, schema-valid example frame."""
        return self._example()


# --- labeled_edges -----------------------------------------------------------

_labeled_edges_schema = pa.DataFrameSchema(
    {
        "edge_id": pa.Column(str, unique=True),
        "metabolite_id": pa.Column(str),
        "gene_id": pa.Column(str),
        "ec": pa.Column(str),
        "label": pa.Column("int8", pa.Check.isin([0, 1])),
        "source": pa.Column("category", pa.Check.isin(["rhea", "brenda"])),
        "reaction_id": pa.Column(str, nullable=True),
        "split": pa.Column("category"),
    },
    strict=True,
    coerce=True,
)


def _labeled_edges_example() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "edge_id": ["e1", "e2"],
            "metabolite_id": ["m1", "m2"],
            "gene_id": ["g1", "g2"],
            "ec": ["1.1.1.1", "2.7.1.1"],
            "label": pd.array([1, 0], dtype="int8"),
            "source": pd.Categorical(["rhea", "brenda"]),
            "reaction_id": ["RHEA:1", "RHEA:2"],
            "split": pd.Categorical(["train", "test"]),
        }
    )


# --- candidate_edges ---------------------------------------------------------

_candidate_edges_schema = pa.DataFrameSchema(
    {
        "edge_id": pa.Column(str, unique=True),
        "metabolite_id": pa.Column(str),
        "gene_id": pa.Column(str),
        "ec": pa.Column(str, pa.Check.str_matches(_EC_REGEX)),
        "analog_score": pa.Column(
            "float32", pa.Check.in_range(0.0, 1.0), nullable=True
        ),
        "precursor_smiles": pa.Column(str, nullable=True),
        "rule_id": pa.Column(str, nullable=True),
        "rule_conf": pa.Column("float32", pa.Check.in_range(0.0, 1.0), nullable=True),
        "rule_diameter": pa.Column("int16", nullable=True),
        "ec_depth": pa.Column("int8", pa.Check.in_range(1, 4), nullable=True),
        "uniprot_tier": pa.Column("int8", nullable=True),
    },
    strict=True,
    coerce=True,
)


def _candidate_edges_example() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "edge_id": ["c1", "c2"],
            "metabolite_id": ["m1", "m2"],
            "gene_id": ["g1", "g2"],
            "ec": ["1.1.1.1", "2.7.1.-"],
            "analog_score": pd.array([0.9, 0.4], dtype="float32"),
            "precursor_smiles": ["CCO", "CC=O"],
            "rule_id": ["r1", "r2"],
            "rule_conf": pd.array([0.8, 0.5], dtype="float32"),
            "rule_diameter": pd.array([6, 4], dtype="int16"),
            "ec_depth": pd.array([4, 3], dtype="int8"),
            "uniprot_tier": pd.array([1, 2], dtype="int8"),
        }
    )


# --- features ----------------------------------------------------------------

_features_schema = pa.DataFrameSchema(
    {
        "edge_id": pa.Column(str, unique=True),
        **{f"f{i:02d}": pa.Column("float32", nullable=True) for i in range(1, 16)},
        r"^.+_missing$": pa.Column("bool", regex=True, required=False),
        "label": pa.Column("int8", pa.Check.isin([0, 1]), nullable=True),
        "split": pa.Column("category"),
        "group": pa.Column(str),
    },
    strict=True,
    coerce=True,
)


def _features_example() -> pd.DataFrame:
    data: dict[str, object] = {"edge_id": ["e1", "e2"]}
    for i in range(1, 16):
        data[f"f{i:02d}"] = pd.array([0.1 * i, 0.2 * i], dtype="float32")
    data["f10_missing"] = pd.array([False, True], dtype="bool")
    data["label"] = pd.array([1, 0], dtype="int8")
    data["split"] = pd.Categorical(["train", "test"])
    data["group"] = ["m1", "m2"]
    return pd.DataFrame(data)


# --- scores ------------------------------------------------------------------

_scores_schema = pa.DataFrameSchema(
    {
        "edge_id": pa.Column(str),
        "model": pa.Column("category"),
        "raw_score": pa.Column(
            "float32", pa.Check(_finite, error="raw_score must be finite")
        ),
        "fold": pa.Column("int8"),
        "oof": pa.Column("bool"),
    },
    unique=["edge_id", "model", "fold"],
    strict=True,
    coerce=True,
)


def _scores_example() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "edge_id": ["e1", "e1"],
            "model": pd.Categorical(["ranker", "rule_score"]),
            "raw_score": pd.array([1.23, -0.4], dtype="float32"),
            "fold": pd.array([0, 0], dtype="int8"),
            "oof": pd.array([True, True], dtype="bool"),
        }
    )


# --- calibrated --------------------------------------------------------------

_calibrated_schema = pa.DataFrameSchema(
    {
        "edge_id": pa.Column(str, unique=True),
        "p_true": pa.Column("float32", pa.Check.in_range(0.0, 1.0)),
        "q_value": pa.Column("float32", pa.Check.in_range(0.0, 1.0)),
        "conformal_set": pa.Column(
            object, pa.Check(lambda s: s.map(lambda x: isinstance(x, list)))
        ),
        "in_region": pa.Column("bool"),
    },
    strict=True,
    coerce=True,
)


def _calibrated_example() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "edge_id": ["e1", "e2"],
            "p_true": pd.array([0.9, 0.2], dtype="float32"),
            "q_value": pd.array([0.05, 0.6], dtype="float32"),
            "conformal_set": pd.Series([["g1"], ["g1", "g2"]], dtype=object),
            "in_region": pd.array([True, False], dtype="bool"),
        }
    )


LabeledEdges = TableSchema(
    "LabeledEdges", _labeled_edges_schema, _labeled_edges_example
)
CandidateEdges = TableSchema(
    "CandidateEdges", _candidate_edges_schema, _candidate_edges_example
)
Features = TableSchema("Features", _features_schema, _features_example)
Scores = TableSchema("Scores", _scores_schema, _scores_example)
Calibrated = TableSchema("Calibrated", _calibrated_schema, _calibrated_example)
