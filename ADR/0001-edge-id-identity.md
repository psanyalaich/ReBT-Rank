# ADR-0001 — Edge identity is `(metabolite, gene)`, not `(metabolite, gene, ec, rule_id)`

- **Status:** Accepted (approved by the project PI, 2026-07-24)
- **Scope:** Design correction to a frozen Engineering Design detail, originating
  from the authoritative Scientific Blueprint.
- **Affects:** M1 (benchmark), M2 (candidates), M3 (features); data model Part 6.

## Context

The data model gives every edge table a primary key `edge_id`. Two frozen
documents specify it differently:

- **Engineering Design, Part 6.1 (original):**
  `edge_id = sha1(metabolite_id | gene_id | ec | rule_id)`, and Part 6.3 states
  *"labels join `labeled_edges → features` on `edge_id`."*
- **Scientific Blueprint (authoritative):** the biological unit of prediction is
  a **`(metabolite, gene)` pair**:
  - Part 3 (M1 downstream interface): *"Emits the canonical **(metabolite, gene)
    key space** that M3 features are joined onto."*
  - Part 4.2 (positives): *"A **(metabolite, gene) pair** is positive if a Rhea
    reaction has that metabolite as a participant and is annotated to a UniProt
    entry whose gene is that gene."*
  - Part 5.1: *"the biological unit of use is 'which genes for this metabolite'."*
  - Output `ranked_edges.csv` is keyed by `(metabolite_id, gene_id)`.

## Conflict

`ec` and `rule_id` are artefacts of **candidate generation**, not of the gold
standard. The gold-standard `labeled_edges` (Rhea/BRENDA) have **no `rule_id`**
(and Part 6.2 assigns them none), so:

1. A gold-standard edge and the candidate edge for the *same biological pair*
   hash to **different `edge_id`s** — the Part 6.3 label join would **never
   match** (a latent correctness bug).
2. Including `ec`/`rule_id` in the key **over-splits** the edge below the
   granularity at which labels, features, ranking, and output are defined. The
   frozen feature set proves aggregation is intended: feature **#6** ("# of
   independent supporting rules") and **#8** ("# analog paths reaching the edge")
   are counts **aggregated across** rules/analogs into **one vector per
   `(metabolite, gene)` edge**.

## Decision & rationale

Per the project's document-precedence rule (Scientific Blueprint is
authoritative and wins all conflicts; Engineering Design is frozen but
subordinate), the Blueprint's `(metabolite, gene)` definition governs. The
Engineering Design's `edge_id` formula is a subordinate implementation detail
that contradicts it, so it is corrected — not the Blueprint.

**Approved replacement:**

```
edge_id = sha1(f"{metabolite_id}|{gene_id}")
```

`metabolite_id` = first-block InChIKey (14 chars); `gene_id` = UniProt accession
(both unchanged from Part 6.1). `reaction_id`, `ec`, `rule_id`, `rule_conf`,
`rule_diameter`, `source`, and similar fields are **supporting evidence /
provenance attached to the edge**, never components of its identity.

Candidate raw evidence may contain multiple rows per edge (per rule / EC /
analog path); **M3 aggregates them into one feature vector per `edge_id`**.

## Downstream modules affected

- **M1 (benchmark):** `labeled_edges` keyed by `edge_id = sha1(metabolite|gene)`;
  one row per `(metabolite, gene)` pair, with `ec` / `source` / `reaction_id`
  retained as provenance columns (collapsed to a representative value / source
  set at the positives-join step, C4).
- **M2 (candidates):** `candidate_edges.edge_id` is the same
  `sha1(metabolite|gene)` key; per-rule/EC/analog columns are evidence, resolved
  by dedup/aggregation so `features.edge_id ⊆ candidate_edges.edge_id` holds.
- **M3 (features):** aggregates candidate evidence per `edge_id`; the label join
  (Part 6.3) is on `edge_id` (= the `(metabolite, gene)` key), which now matches
  across `labeled_edges` and `features`.

## Interface impact

- **B2 (`common.types`):** unaffected — `RunManifest` / `MetricResult` do not
  reference `edge_id`. **No public interface changed.**
- **B3 (`common.config`):** unaffected — no config field references `edge_id`.
  **No public interface changed.**
- **B5 (`common.schemas`):** **no structural change.** The Pandera schemas type
  `edge_id` as a `str` primary-key column; they do not encode its derivation
  formula. Only the *computation* of `edge_id` (M1/M3 code) and the Part 6.1/6.3
  spec wording change. Column sets for `LabeledEdges`, `CandidateEdges`,
  `Features`, `Scores`, `Calibrated` are unchanged; `ec` remains a provenance
  column on the tables that already declared it.

No frozen public API is broken by this amendment.
