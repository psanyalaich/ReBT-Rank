"""ReBT-Rank: a benchmarked, confidence-calibrated, false-discovery-controlled
re-ranking layer over reverse-biotransformation-derived metabolite-gene hypotheses.

This package is implemented module-by-module (M0-M7 plus ``common`` and a thin
orchestrator) following the frozen Engineering Design task graph. Task A1 provides
only the package skeleton and the ``rebt-rank`` console-script entry point; the
public API is re-exported here as the modules land.
"""

__version__ = "0.0.1"

__all__ = ["__version__"]
