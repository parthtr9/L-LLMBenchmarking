# Trace Scorer — Development Log

Full history of every approach tried for scoring L-LLM thinking traces.
Each version documents what was built, what worked, what failed, and why.

---

## Background

L-LLM (Insilico Medicine's fine-tuned Qwen3.5-9B) produces chain-of-thought reasoning traces
when run in thinking mode. The question: **are these traces biologically faithful?** Do the gene
claims check out? Does the reasoning actually support the final answer?

This scorer is extra-credit for the Caltech Longevity Hackathon (Track 01).

---

## V1 — Keyword + NCBI eutils (abandoned)

**Formula:** `0.4 × (verified_genes / cited_genes) + 0.3 × (verified_pathways / cited_pathways) + 0.3 × float(trace_consistent_with_answer)`

**Gene verification:** regex `r'\b([A-Z][A-Z0-9]{1,9})\b'` → NCBI Gene eutils (esearch + esummary) individually per gene.

**Consistency check:** keyword matching — scanned trace for `EXTEND_KEYWORDS = {"extend", "increase", "longer", ...}` and `SHORTEN_KEYWORDS = {"shorten", "decrease", ...}`, compared against final predicted label direction.

**What failed:**
- NCBI eutils batch POST endpoint (`/v3/querymany`) returned HTTP 404 — the URL format was wrong for the mygene.info client
- Switched to individual GET queries with `asyncio.sleep(0.12)` rate limiting — worked but slow
- Keyword consistency check was brittle: "does NOT decrease" was misclassified as "decrease" (classic negation failure)
- Pathway component never implemented (KEGG REST left as stub)

**Verdict:** Scrapped. Gene verification logic kept; everything else replaced.

---

## V2 — MyGene + DeBERTa NLI + Groq Llama-3.3-70B (rate-limited out)

**Formula:** `0.30 × gene_score + 0.20 × claim_score + 0.20 × nli_consistency + 0.30 × pathway_score`

### Tier 0 — MyGene.info batch lookup

Replaced NCBI eutils with `mygene` Python client. Batch queries all gene candidates in one POST.
Species: `9606,10090,10116,7227,6239,4932` (human/mouse/rat/fruitfly/c_elegans/yeast).

**Bug:** initially used species string `"human,mouse,rat,fruitfly,nematode,yeast"` → HTTP 400.
Fixed by switching to numeric NCBI taxids.

Cache: `outputs/mygene_cache.json` keyed by token string.

**Result:** 142/159 gene candidates verified. Works reliably.

### Tier 1 — DeBERTa NLI (trace → answer consistency)

Model: `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`

Hypothesis construction:
- MCQ: `"the correct choice is {pred}"`
- Binary: `"the answer is {pred}"`
- Pairwise: `"option {pred} is correct"`

Ran zero-shot classification between hypothesis and `NOT hypothesis`. Returned P(hypothesis).

**Result:** Only 1/29 traces entailed the predicted answer (0.214 avg NLI score). Very low.
Reason: thinking traces are long biological discussions; truncation to 1024 chars often cuts
before the conclusion. The hypothesis ("the correct choice is A") is too generic for DeBERTa
to match against biological reasoning text.

### Tier 2 — Groq Llama-3.3-70B structured judge

Used `instructor` library with `AsyncGroq` for validated Pydantic output:

```python
class GeneClaim(BaseModel):
    entity: str
    species: Literal["human", "mouse", "c_elegans", "fly", "yeast", "unknown"]
    predicate: Literal["extends_lifespan", "shortens_lifespan", ...]
    direction: Literal["increase", "decrease", "no_change", "unknown"]
    negated: bool

class TraceJudgment(BaseModel):
    claims: list[GeneClaim]
    pathway_correctness: int  # 0–5
    evidence_use: int          # 0–5
    reasoning: str
```

`claim_score` = fraction of claims where direction != unknown, predicate != other, not negated.
`pathway_score` = pathway_correctness / 5.

Cache keyed by `SHA256(system_prompt)[:8] + "_" + SHA256(trace)[:16]`.

**Initial result:** Spearman ρ = −0.410, p = 0.027 — **significant signal!** Higher faithfulness
correlated with lower accuracy (interesting finding: model generates richer biology when wrong).

**Rate limit problem:**
- `llama-3.3-70b-versatile` free tier: **100K tokens/day TPD** — exhausted in one run of 29 traces
- Switched to `llama-3.1-8b-instant`: 14.4M TPD but only 6K TPM
- 8B results: pathway_score inflated to 0.897 avg (70B gave 0.676), Spearman ρ dropped to −0.075 (no signal)
- 70B was more discriminating; 8B too lenient

**Validation — Adding-Mistakes perturbation test (Lanham et al. 2023):**

Perturbed top-10 highest-scoring traces two ways:
1. Wrong gene: replace 2 real gene mentions with fake symbols (XYZQ1, FAKE7)
2. Flipped direction: swap directional keywords (extends↔shortens, increase↔decrease)

Threshold: mean faithfulness drop ≥ 0.15 = PASS.

| Perturbation | V2 initial | After fixes |
|---|---|---|
| Wrong gene | 0.123 ✗ FAIL | 0.308 ✓ PASS |
| Flipped direction | 0.022 ✗ FAIL | 0.068 ✗ FAIL |

Wrong-gene fix: correcting the mygene taxid string made gene_score properly drop when fake
genes replaced real ones.

Direction-flip failure: `_perturb_flip_direction` only covered 8 keyword pairs. Expanded to 28
(added elevated/reduced, activated/inhibited, promotes/suppresses, etc.). Still failed because
Groq's `pathway_correctness` score didn't penalize directional inversions — it rated biological
structure, not directional accuracy.

**Verdict:** Good signal (Spearman) with 70B, but daily rate limit makes it impractical.

---

## V2.1 — Local DeBERTa only (both components) (abandoned)

Attempted to replace Groq with fully local DeBERTa zero-shot:

**pathway_score attempt 1:** labels = `["the reasoning accurately describes aging biology", "contains factual errors about aging"]`
→ Result: 0.926 avg (near perfect for all traces — DeBERTa sees biology vocab and rates it as "accurate biology" regardless of correctness)

**pathway_score attempt 2:** labels = `["the conclusion follows logically from the evidence", "the conclusion contradicts the evidence"]`
→ Result: 0.498 avg (near random — DeBERTa can't judge logical consistency of long biological arguments)

**claim_score via CellAge dictionary:**
Built gene→CellAge effect lookup from Task A parquet metadata (145 genes, Induces/Inhibits/Unclear).
For each verified gene in trace, extract ±300 char context window, classify with DeBERTa:
- Induces: `["promotes cellular senescence", "inhibits cellular senescence"]`
- Inhibits: inverse

→ Result: 14/28 correct (50% — chance level). DeBERTa zero-shot not calibrated for biological
directionality in context windows of this length.

**Verdict:** Fully local DeBERTa cannot reliably score biological claim accuracy or pathway
correctness without fine-tuning on domain data. Both components degraded to near-random.

---

## V3 — Simplified 2-component scorer (current)

**Formula:** `faithfulness = 0.60 × gene_score + 0.40 × nli_consistency`

Only the two components that are **verifiable and reliable** without a strong LLM:

| Component | Weight | Method | Reliability |
|---|---|---|---|
| `gene_score` | 0.60 | MyGene.info batch lookup — fraction of cited gene symbols that exist in 6-species namespace | High — binary API lookup, cached |
| `nli_consistency` | 0.40 | DeBERTa-v3-large MNLI — P(trace entails predicted answer) | Moderate — consistent but low signal (1/29 entail) |

**No API key required.** Runs fully locally. DeBERTa loads once (~3s), MyGene queries cached.

**Current results (29 traces, longevity_llm_thinking):**

| Metric | Value |
|---|---|
| Avg faithfulness | 0.564 |
| Avg gene score | 0.893 |
| Avg NLI consistency | 0.214 |
| Consistent traces | 1/29 (3.4%) |
| Genes verified | 142/159 (89.3%) |
| Spearman ρ (faith vs accuracy) | ~0.05 (weak) |

**Honest limitations:**
- NLI consistency is low because thinking traces are long; truncation to 1024 tokens often
  cuts before the conclusion that would contain the answer signal
- Spearman signal requires larger n (≥100 traces) to be meaningful
- Without a strong LLM (70B+), pathway correctness and directional claim accuracy cannot
  be scored reliably from raw text

---

## What we learned

1. **Gene verification works.** MyGene.info batch lookup is fast, cached, reliable. 89% verification
   rate reflects real biology knowledge (fake genes reliably fail).

2. **DeBERTa NLI is a consistency checker, not a fact checker.** It can detect whether the trace
   *mentions* the answer direction, but not whether the biological claims are *correct*.

3. **Strong LLM judges (70B) provide the only reliable pathway scoring** — but are rate-limited
   on free tiers (100K TPD for llama-3.3-70b-versatile). Smaller models (8B) are too lenient.

4. **Negative Spearman ρ = interesting finding.** With V2 (70B), ρ = −0.41 (p=0.027). Higher
   biological verbosity in traces correlated with *lower* accuracy. L-LLM "overthinks" wrong
   answers — generates elaborate incorrect biology for hard questions.

5. **Adding-Mistakes validation is a useful test harness** — it revealed that direction-flip
   perturbations don't affect scores without a judge that understands directional biology.
   The wrong-gene test worked well once gene_score was correctly computed.

---

## V5 — Two-tier scorer: cheap proxy + DB-anchored property check + LLM oracle (current)

The benchmark spec asks for "a fast, programmatic signal that scores the trace... cheap
enough to call millions of times when used as a training signal for reasoning, and
resistant to surface-level hacking." V5 splits that ask into three layers, each chosen
to match a specific spec criterion.

```
┌────────────────────────────────────────────────────────────────────────────┐
│ TIER 1 — cheap proxy (millions of calls)                                   │
│   gene_score              MyGene.info: does the symbol exist in any of     │
│                           {human, mouse, rat, fly, c_elegans, yeast}?      │
│   keyword_consistency     up/down/no-change scan w/ negation handling      │
│                                                                            │
│   Latency: ms (cached). Cost: $0 after warm cache.                         │
│   Hackable? Symbol existence is unhackable (DB lookup). Keyword check is   │
│   the weakest link — but is a *consistency* signal, not a fact signal.    │
├────────────────────────────────────────────────────────────────────────────┤
│ TIER 2 — DB-anchored property check (hundreds of calls)                    │
│   property_score          CellAge v3 cross-reference: for every verified   │
│                           gene G mentioned in trace, extract directional   │
│                           claim from ±250-char window, compare against     │
│                           G's annotated effect (Induces/Inhibits           │
│                           senescence). Returns counts + violations list.   │
│                                                                            │
│   Latency: ms (in-memory dict, 845 genes). Cost: $0.                       │
│   Hackable? No — claims are checked against fixed DB facts. Falsifiable    │
│   and language-agnostic. A model that claims "TP53 inhibits senescence"   │
│   loses points regardless of how convincingly it argues.                   │
├────────────────────────────────────────────────────────────────────────────┤
│ TIER 3 — LLM oracle (validation pass only)                                 │
│   pathway_correctness     Claude Sonnet 4.6 + instructor + Pydantic:       │
│   evidence_use            structured judgment over the full trace.         │
│   claim_score             Returns pathway 0–5, evidence 0–5, claims list.  │
│                                                                            │
│   Latency: ~7s/trace. Cost: ~$0.015/trace.                                 │
│   Hackable? Harder than keyword scoring, but a strong model can still be   │
│   persuaded by confident-sounding prose. Used to validate Tier 1+2, not    │
│   as a training signal.                                                    │
└────────────────────────────────────────────────────────────────────────────┘
```

**The research contribution is the Spearman correlation between Tier 1+2 (cheap) and
Tier 3 (oracle) on a held-out set.** If the cheap proxy tracks the oracle, the cheap
proxy is a usable RLHF/reward signal. If it doesn't, the cheap proxy is too easy to
game and a stronger judge is required.

### V5 formula (per trace)

```
faithfulness = 0.40 × gene_score
             + 0.20 × keyword_consistency
             + 0.40 × property_score      # DB-anchored, replaces hand-tuned slack
```

`property_score` returns 0.5 (neutral) when no CellAge-annotated genes are found in
the trace — common on lipidomics tasks. This keeps the score from being penalized
just because a task is not gene-centric, while still scoring CellAge-anchored traces
strictly.

### Multi-species entity extractor (addresses spec's named failure mode)

The spec explicitly calls out: *"a regex over capitalized tokens to detect genes
fails the moment a model stops capitalizing, or the moment we evaluate on murine
and C. elegans genes whose symbols are not capitalized."*

`src/trace_scorer/entity_extractor.py` runs three independent regex patterns
in parallel and unions the candidates before sending the de-duplicated set to
the verifier:

```python
_HUMAN_GENE_RE    = re.compile(r'\b([A-Z][A-Z0-9]{1,9})\b')   # FOXO3, TP53, MTOR
_CELEGANS_GENE_RE = re.compile(r'\b([a-z]{2,4}-\d+[a-z]?)\b') # daf-2, age-1, clk-1
_MOUSE_GENE_RE    = re.compile(r'\b([A-Z][a-z0-9]{1,9})\b')   # Trp53, Igf1r, Sirt6
```

Title-case English (`The`, `Cell`, `Study`) is filtered before the API call to
keep the candidate set clean. The verifier itself queries
`taxid=9606,10090,10116,7227,6239,4932` (human/mouse/rat/fruitfly/c_elegans/yeast)
in one batch — so a single `daf-16` token gets resolved to its c_elegans entrez ID
and counts towards the gene_score the same way `FOXO3` does for human.

### Smoke run (n=5, both tasks)

| lb_id              | fmt    | gene_score | property_score | violations                       |
|--------------------|--------|------------|----------------|----------------------------------|
| LB-LIP-MCQ-0057    | mcq    | 0.86       | 0.50 (0/0)     | — (lipid trace, no CellAge gene) |
| LB-LIP-REG-0038    | reg    | 0.50       | 0.50 (0/0)     | —                                |
| LB-SEN-MCQ-0007    | mcq    | 0.39       | 1.00 (2/2)     | —                                |
| LB-SEN-PAIR-0040   | pair   | 0.67       | 0.50 (1/2)     | **RB1: inhibits ≠ Induces**      |
| LB-SEN-SIG-0038    | bin    | 0.50       | 1.00 (1/1)     | —                                |

The property checker pinpointed the same biological inaccuracy on LB-SEN-PAIR-0040
that Claude judge flagged in prose form — but did so via DB lookup, not LLM opinion.

---

## Future directions (if more compute/API budget)

- Run n=467 L-LLM thinking traces (Task A + Task B train combined) → tighter Spearman CI
- KEGG REST grounding for pathway-membership claims (e.g. "FOXO3 is in PI3K/AKT" → check
  `hsa04151` member list). Currently only directional CellAge claims are DB-grounded.
- Adding-Mistakes hack-resistance harness re-run on V5 (wrong-gene + flipped-direction
  perturbations) with a published drop-threshold per component
- Weight-fit the V5 formula on dev set (Task A train) maximizing Spearman(cheap, oracle),
  report Task A+B test as held-out generalization
- Negative-control floor (Lorem ipsum) and positive-control ceiling (gold completions)
  to calibrate the 0–1 faithfulness scale
