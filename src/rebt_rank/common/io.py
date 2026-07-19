"""Validated, atomic file I/O for ReBT-Rank (Task B4).

The single I/O boundary for the pipeline: parquet/JSON read/write with optional
schema validation, and an :class:`ArtifactWriter` that writes a table plus its
sidecar provenance manifest.

Scope (agreed for B4):

* Schema validation is expressed through the minimal structural
  :class:`SupportsValidate` protocol -- the frozen ``validate(df) -> df``
  contract of Engineering Design Part 3.1. The concrete Pandera schemas arrive
  in B5 and satisfy this protocol without B4 depending on Pandera.
* Sidecar manifests are serialized via :meth:`RunManifest.to_dict` (B2), NOT
  ``RunManifest.write`` (M0c), preserving the B4/M0c boundary.
* Writes are atomic **per file** (temp file + :func:`os.replace`). The parquet
  and its sidecar manifest are each replaced atomically, but the pair is not a
  single transaction: a crash between the two can leave a table without its
  manifest.
* JSON is serialized deterministically (``indent=2``, ``sort_keys=True``,
  ``ensure_ascii=False``) for reproducible, diff-stable output.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, Self

import pandas as pd

from rebt_rank.common.types import RunManifest

__all__ = [
    "SupportsValidate",
    "read_json",
    "write_json",
    "read_parquet",
    "write_parquet",
    "ArtifactWriter",
]

_MANIFEST_SUFFIX = ".manifest.json"


class SupportsValidate(Protocol):
    """Structural type for schema objects: validate a frame and return it.

    Matches the frozen ``SchemaRegistry.validate(df) -> df`` contract (Part 3.1).
    B5's Pandera schemas satisfy this protocol; B4 depends only on the shape.
    """

    def validate(self, df: pd.DataFrame) -> pd.DataFrame: ...


def _dumps_json(obj: Any) -> str:
    """Serialize ``obj`` to deterministic, diff-stable JSON."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically via a temp file in the same dir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _manifest_path(path: Path) -> Path:
    """Return the sidecar-manifest path for an artifact ``path``."""
    return path.with_name(path.name + _MANIFEST_SUFFIX)


def write_json(obj: Any, path: Path) -> Path:
    """Atomically write ``obj`` as deterministic JSON; return ``path``."""
    _atomic_write_bytes(path, _dumps_json(obj).encode("utf-8"))
    return path


def read_json(path: Path) -> Any:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def read_parquet(path: Path, schema: SupportsValidate | None = None) -> pd.DataFrame:
    """Read a parquet file, validating against ``schema`` when provided."""
    df = pd.read_parquet(path)
    if schema is not None:
        df = schema.validate(df)
    return df


def write_parquet(
    df: pd.DataFrame,
    path: Path,
    *,
    schema: SupportsValidate | None = None,
    manifest: RunManifest,
) -> Path:
    """Validate (if ``schema``) and atomically write ``df`` plus its sidecar
    manifest; return ``path``.

    ``schema`` and ``manifest`` are keyword-only: this keeps the Part 3.1
    parameter order (schema, manifest) while making ``manifest`` required and
    ``schema`` optional (there are no schemas until B5).
    """
    with ArtifactWriter(path, manifest) as writer:
        writer.write_table(df, schema=schema)
    return path


class ArtifactWriter:
    """Context manager writing a table plus its sidecar manifest.

    On clean exit the parquet and its ``<path>.manifest.json`` sidecar are each
    committed atomically (temp file + :func:`os.replace`). If the ``with`` body
    raises, nothing is committed.
    """

    def __init__(self, path: Path, manifest: RunManifest) -> None:
        self._path = path
        self._manifest = manifest
        self._table: pd.DataFrame | None = None

    def write_table(
        self, df: pd.DataFrame, schema: SupportsValidate | None = None
    ) -> None:
        """Stage ``df`` for commit, validating against ``schema`` when provided."""
        self._table = schema.validate(df) if schema is not None else df

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            return  # propagate the exception; commit nothing
        self._commit()

    def _commit(self) -> None:
        if self._table is None:
            raise ValueError("ArtifactWriter: no table was written before commit")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(f".{self._path.name}.tmp-{os.getpid()}")
        try:
            self._table.to_parquet(tmp, index=False)
            os.replace(tmp, self._path)
        finally:
            if tmp.exists():
                tmp.unlink()
        write_json(self._manifest.to_dict(), _manifest_path(self._path))
