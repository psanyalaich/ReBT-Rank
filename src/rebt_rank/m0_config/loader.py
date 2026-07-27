"""Configuration loading and overlay resolution for ReBT-Rank (Task M0a).

Implements the public entry point :func:`load_config` (Engineering Design Part
4.2): read a YAML config file, resolve its ``extends: [...]`` inheritance chain
(Part 5.1) by deep-merging referenced configs deepest-last, build the immutable
:class:`~rebt_rank.common.config.Config`, and log the resolved config hash. Any
pydantic validation failure (unknown keys, wrong types, missing fields) surfaces
as :class:`~rebt_rank.common.errors.ConfigError`.

Scope (M0a): YAML parsing plus ``extends`` / ``overlay`` resolution plus Config
construction only. Snapshot verification (M0b) and RunManifest assembly (M0c)
live in their own tasks. Path resolution (Part 5.2, ``REBT_ROOT`` + output-dir
creation) is deferred until a task first consumes ``cfg.paths``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from omegaconf.errors import OmegaConfBaseException
from pydantic import ValidationError

from rebt_rank.common.config import Config, _deep_merge
from rebt_rank.common.errors import ConfigError
from rebt_rank.common.logging import get_logger

__all__ = ["load_config"]

_logger = get_logger(__name__)
_CONFIGS_DIR_NAME = "configs"
_EXTENDS_KEY = "extends"


def load_config(path: Path, overlay: str | None = None) -> Config:
    """Load, resolve, and validate a run configuration (Part 4.2 / 5.1).

    ``path`` is a YAML file whose optional ``extends: [name, ...]`` list names
    other configs; each is resolved against the ``configs`` root and merged
    deepest-last, recursively, with the file's own keys overriding its parents.
    ``overlay``, when given, names one further config merged on top of the whole
    result. The merged mapping is validated into an immutable :class:`Config`
    and its content hash is logged.

    Raises :class:`ConfigError` when a referenced file is missing, cannot be
    parsed, does not describe a mapping, forms an ``extends`` cycle, or fails
    :class:`Config` validation.
    """
    path = Path(path)
    root = _configs_root(path)
    merged = _resolve(path, root, frozenset())
    if overlay is not None:
        overlay_merged = _resolve(root / f"{overlay}.yaml", root, frozenset())
        merged = _deep_merge(merged, overlay_merged)
    try:
        config = Config(**merged)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration from {path}: {exc}") from exc
    _logger.info("config.loaded", path=str(path), config_hash=config.hash())
    return config


def _configs_root(path: Path) -> Path:
    """Return the root against which ``extends`` names resolve.

    The nearest ancestor directory named ``configs`` (the frozen Part 2 layout);
    falls back to the file's own directory when there is no such ancestor.
    """
    for parent in path.parents:
        if parent.name == _CONFIGS_DIR_NAME:
            return parent
    return path.parent


def _resolve(path: Path, root: Path, seen: frozenset[Path]) -> dict[str, Any]:
    """Recursively resolve ``path``'s ``extends`` chain into one merged mapping.

    Parents are merged in list order (deepest-last); the file's own keys then
    override them. ``seen`` carries the resolved paths on the current branch to
    detect ``extends`` cycles.
    """
    resolved = path.resolve()
    if resolved in seen:
        raise ConfigError(f"Circular 'extends' detected at {path}")
    seen = seen | {resolved}
    raw = _load_yaml(path)
    parents = _extends_list(raw.pop(_EXTENDS_KEY, []), path)
    merged: dict[str, Any] = {}
    for name in parents:
        merged = _deep_merge(merged, _resolve(root / f"{name}.yaml", root, seen))
    return _deep_merge(merged, raw)


def _extends_list(value: Any, path: Path) -> list[str]:
    """Normalize an ``extends`` value to a list of config names."""
    names = [value] if isinstance(value, str) else value
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ConfigError(f"'extends' in {path} must be a string or a list of strings")
    return names


def _load_yaml(path: Path) -> dict[str, Any]:
    """Parse a single YAML file into a plain mapping (no ``extends`` handling)."""
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        container = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    except (OmegaConfBaseException, OSError, ValueError) as exc:
        raise ConfigError(f"Could not parse YAML config {path}: {exc}") from exc
    if not isinstance(container, Mapping):
        raise ConfigError(f"Config {path} must be a mapping at the top level")
    return dict(container)
