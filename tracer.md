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

## Future directions (if more compute/API budget)

- Fine-tune a small biomedical NLI model (BioLinkBERT or PubMedBERT) on senescence-specific
  claim pairs derived from Task A ground truth + CellAge annotations
- Use Groq 70B with sequential calls + exponential backoff to stay under TPM (not TPD)
- Expand n from 29 → full test set (59 samples) for meaningful Spearman CI
- Per-gene directional scoring using sentence-level extraction + CellAge cross-reference
