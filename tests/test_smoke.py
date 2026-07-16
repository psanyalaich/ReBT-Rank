"""Smoke test for Task A3.

Confirms the package imports and exposes a version string, so the CI test stage
is green on an otherwise-empty suite. Real tests are added by later tasks.
"""

from __future__ import annotations

import rebt_rank


def test_package_exposes_version_string() -> None:
    assert isinstance(rebt_rank.__version__, str)
    assert rebt_rank.__version__
