# L-LLMBenchmarking

Caltech Longevity Hackathon Track 01 — LongevityLLM Benchmarking.
Evaluates L-LLM (Insilico Medicine's fine-tuned Qwen3.5-9B) against Claude Sonnet and baselines on Task A (senescence perturbation). Includes a trace faithfulness scorer that verifies biological claims in L-LLM's chain-of-thought.

**Stack:** Inspect AI · LiteLLM · BioThings mygene.info · static React dashboard

---

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Fill in .env
```

### Required env vars

| Var | Required | Notes |
|-----|----------|-------|
| `HF_TOKEN` | Yes | Classic read token from huggingface.co/settings/tokens |
| `HF_ENDPOINT_URL` | Yes for L-LLM | vLLM endpoint from organizers |
| `ANTHROPIC_API_KEY` | For claude_sonnet | Anthropic Console key |

Never commit `.env`.

---

## Full pipeline (run in order)

### 1. Run eval on Task A test set

```bash
# All models — standard mode (no thinking traces)
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test.parquet \
  --models longevity_llm,claude_sonnet,majority_baseline,random_baseline

# L-LLM with thinking mode enabled (needed for trace scorer)
# Uses balanced 30-sample subset — 10 per format (mcq / binary / pairwise)
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test_30.parquet \
  --models longevity_llm_thinking \
  --max-tokens 3000
```

Logs written to `outputs/inspect/<model_name>/`.

### 2. Export logs → dashboard JSON

```bash
.venv/bin/python -m tools.export_inspect_logs \
  --log-dir outputs/inspect \
  --out "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"
```

### 3. Score thinking traces (faithfulness)

```bash
.venv/bin/python -m src.trace_scorer.trace_scorer
```

Reads `public/data.json`, verifies gene symbols via NCBI mygene.info, checks trace-answer consistency.
Writes to `outputs/trace_faithfulness_scores.json` and `public/trace_faithfulness_scores.json`.

### 4. Serve dashboard

```bash
cd "LongevityBench Design System/ui_kits/longevity_bench"
python3 -m http.server 8765
# open http://localhost:8765/
```

Must serve from this directory — CSS tokens and JSON files resolve relative to it.

---

## Model registry

Models defined in [config/models.yaml](config/models.yaml). Add providers there without touching Python.

Available: `longevity_llm`, `longevity_llm_thinking`, `claude_sonnet`, `random_baseline`, `majority_baseline`.

---

## Dashboard views

| View | What it shows |
|------|--------------|
| Trust & reasoning | Trace faithfulness scores, gene verification, consistency — click any metric for explanation |
| Eval matrix | Per-sample × per-model pass/fail table from real eval data |
| Compare models | Aggregate scores per model per task |
| Answers | Full sample list with pred / gold, filterable |
| Live runs | Eval run history |

---

## Architecture

```
Task A parquet
    ↓
run_inspect.py  →  parquet_task (@task)
                       ├── litellm_solver    →  L-LLM / Claude / baselines
                       └── longebench_scorer →  mcq / binary / pairwise
                ↓
         outputs/inspect/<model>/*.eval
                ↓
export_inspect_logs.py  →  public/data.json
                ↓
trace_scorer.py  →  entity_extractor + ncbi_verifier + consistency_checker
                 →  public/trace_faithfulness_scores.json
                ↓
         Dashboard (static React, no backend)
```

---

## Task A — Senescence

300 prompts across three formats derived from the Senescent Fibroblast Transcriptome Compendium filtered through CellAge v3.

| Format | Task | Metric |
|--------|------|--------|
| MCQ | Predict direction of gene expression change (A=up / B=down / C=no change) | Accuracy |
| Binary | Predict whether perturbation produces a significant change (A/B) | Accuracy |
| Pairwise | Predict which of two genes shows a larger absolute expression change | Accuracy |

Train/test split by GEO accession — no random split (comparisons within a study share batch effects).

### Regenerate prompts

```bash
cd data/task_a_senescence
python senescence_benchmark_pipeline.py \
  --dataset raw/Total_Data.csv \
  --cellage raw/cellage3.tsv \
  --output-dir processed
```

---

## Trace faithfulness scorer

Scores L-LLM thinking traces for biological grounding.

```
faithfulness = (0.4 × gene_score + 0.3 × consistency) / 0.7

gene_score  = verified_genes / cited_genes   (NCBI mygene.info)
consistency = 1.0 if trace direction matches predicted answer else 0.0
```

Cache saved to `outputs/verifier_cache.json` — re-runs use cached gene lookups.
