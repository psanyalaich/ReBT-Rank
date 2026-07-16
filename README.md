# ReBT-Rank

**A benchmarked, confidence-calibrated, false-discovery-controlled framework for
prioritizing reverse-biotransformation-derived metabolite–gene hypotheses.**

ReBT-Rank is a re-ranking layer that sits *on top of* an existing reverse-
biotransformation pipeline (Smruti Rekha & Aich, *J. Proteome Res.* 2026). It
consumes that pipeline's candidate metabolite→gene edges and, for each edge,
emits a ranking score, a calibrated probability, a target–decoy q-value, and a
human-readable rationale — turning an unranked hypothesis cloud into a short,
statistically interpretable shortlist.

## Status

Pre-alpha. The package is being built module-by-module (M0–M7). This is the
initial scaffold (Task A1): a `pip`-installable package exposing the `rebt-rank`
console script.

## Install (development)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  POSIX:  source .venv/bin/activate
pip install -e .
rebt-rank --help
```

Target interpreter: **Python ≥ 3.11**.

## License

Code is released under the [MIT License](LICENSE). The released Rhea/BRENDA-
derived benchmark artifact is CC BY 4.0; KEGG is used query-only and never
redistributed.
