# L-LLMBenchmarking

Caltech Longevity Hackathon Track 01 — LongevityLLM Benchmarking.
Evaluates L-LLM (Insilico Medicine's fine-tuned Qwen3.5-9B) against Claude Sonnet 4.5 and baselines on two novel benchmark tasks:

- **Task A — Senescence Perturbation** (298 prompts): Gene-level differential expression prediction across senescence perturbation experiments
- **Task B — Lipidomics** (285 prompts): Age bracket, numeric age, and diabetes prediction from plasma lipid profiles

Includes a V4 trace faithfulness scorer that verifies biological claims in L-LLM's chain-of-thought traces against mygene.info.

**Stack:** Inspect AI · LiteLLM · BioThings mygene.info · static React dashboard (no build step)

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
| `HF_ENDPOINT_URL` | Yes for L-LLM | vLLM-compatible endpoint from organizers (OpenAI-compat format) |
| `ANTHROPIC_API_KEY` | Yes for claude_sonnet | Anthropic Console key |

Never commit `.env`.

---

## Full pipeline (run in order)

### 1. Run eval

```bash
# Task A — all 4 models on test set
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test.parquet \
  --models longevity_llm,claude_sonnet,majority_baseline,random_baseline

# Task A — L-LLM with thinking traces (30-sample subset, 10 per format)
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test_30.parquet \
  --models longevity_llm_thinking \
  --max-tokens 3000

# Task B — all 4 models on test set
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_b_lipidomics/task_b_lipidomics_test.parquet \
  --models longevity_llm,claude_sonnet,majority_baseline,random_baseline
```

Logs written to `outputs/inspect/<model_name>/`.

### 2. Export logs → dashboard JSON

```bash
.venv/bin/python -m tools.export_inspect_logs \
  --log-dir outputs/inspect \
  --out "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"
```

### 3. Run gap analysis

```bash
.venv/bin/python -m src.analysis.gap_analysis
```

Reads `public/data.json`. Writes:
- `outputs/gap_analysis_report.md` — human-readable markdown
- `public/gap_analysis_data.json` — structured JSON consumed by dashboard Gap Analysis view

### 4. Score thinking traces (faithfulness)

```bash
.venv/bin/python -m src.trace_scorer.trace_scorer
```

Reads `public/data.json`, verifies gene symbols via mygene.info API (cached in `outputs/mygene_cache.json`), applies keyword consistency checker.
Writes `outputs/trace_faithfulness_scores.json` and `public/trace_faithfulness_scores.json`.

### 5. Export task data for dashboard library views

```bash
python3 << 'EOF'
import pandas as pd, json
from pathlib import Path

PUBLIC = Path("LongevityBench Design System/ui_kits/longevity_bench/public")

def extract_row(row, split):
    msgs = row['messages']
    if isinstance(msgs, str): msgs = json.loads(msgs)
    user_msg = next((m['content'] for m in msgs if m['role'] == 'user'), '')
    gold = next((m['content'] for m in msgs if m['role'] == 'assistant'), '')
    meta = row.get('metadata') or '{}'
    if isinstance(meta, str):
        try: meta = json.loads(meta)
        except: meta = {}
    return {
        'lb_id': row['lb_id'], 'format': row['format'], 'pool': row['pool'],
        'display_group': row.get('display_group', ''), 'domain': row['domain'],
        'metric': row['metric'], 'split': split,
        'question': user_msg[:1000], 'gold': gold,
        'follow_up': (meta.get('follow_up','') or '')[:400] if isinstance(meta,dict) else '',
    }

for task, paths in [
    ('task_a', {'train': 'data/task_a_senescence/processed/task_a_senescence_train.parquet',
                'test':  'data/task_a_senescence/processed/task_a_senescence_test.parquet'}),
    ('task_b', {'train': 'data/task_b_lipidomics/task_b_lipidomics_train.parquet',
                'test':  'data/task_b_lipidomics/task_b_lipidomics_test.parquet'}),
]:
    rows = []
    for split, path in paths.items():
        df = pd.read_parquet(path)
        rows.extend(extract_row(r, split) for _, r in df.iterrows())
    (PUBLIC / f'{task}_data.json').write_text(json.dumps({'task': task, 'rows': rows}, indent=2))
    print(f"{task}: {len(rows)} rows")
EOF
```

### 6. Serve dashboard

```bash
cd "LongevityBench Design System/ui_kits/longevity_bench"
python3 -m http.server 8765
# open http://localhost:8765/
```

Must serve from this directory — CSS tokens and JSON files resolve relative to it.

---

## Current benchmark results

All results on test split. Balanced accuracy for classification; MAE for regression.

### Task A — Senescence Perturbation (n=104 evaluated)

| Model | MCQ (bal acc) | Binary (bal acc) | Pairwise (acc) | Regression (MAE) |
|-------|--------------|-----------------|----------------|-----------------|
| L-LLM | 0.367 | 0.500 | 0.556 | 10.571 |
| Claude Sonnet 4.5 | 0.258 | 0.500 | **0.778** | 25.787 |
| Majority baseline | 0.171 | 0.500 | 0.500 | — |
| Random baseline | 0.258 | 0.389 | 0.667 | — |

L-LLM leads on MCQ and regression (lower MAE); Claude leads on pairwise.

### Trace faithfulness (L-LLM thinking, n=29 traces)

| Metric | Value |
|--------|-------|
| Formula | `0.60 × gene_score + 0.40 × keyword_consistency` |
| Avg faithfulness | 0.716 |
| Gene score (mygene.info) | 0.895 (89.5% of cited genes verified) |
| Keyword consistency | 0.448 (24.1% directionally consistent) |
| Spearman ρ (faithfulness vs correctness) | 0.034 (p=0.861, n=29 — not yet significant) |

Keyword consistency is low because biological traces discuss mechanisms rather than stating direction explicitly. Increase n for statistical power.

---

## Model registry

Models defined in [config/models.yaml](config/models.yaml). Add providers without touching Python.

```yaml
models:
  longevity_llm:
    litellm_model: "openai/longevity-llm"
    api_base_env: "HF_ENDPOINT_URL"
    api_key_env: "HF_TOKEN"
    extra_body:
      chat_template_kwargs: {enable_thinking: false}
    max_concurrency: 8

  longevity_llm_thinking:
    litellm_model: "openai/longevity-llm"
    api_base_env: "HF_ENDPOINT_URL"
    api_key_env: "HF_TOKEN"
    extra_body:
      chat_template_kwargs: {enable_thinking: true}
    max_concurrency: 4

  claude_sonnet:
    litellm_model: "anthropic/claude-sonnet-4-6"
    api_key_env: "ANTHROPIC_API_KEY"
    max_concurrency: 4

  random_baseline:
    type: baseline
    strategy: random

  majority_baseline:
    type: baseline
    strategy: majority
```

---

## Dashboard views

| View | What it shows | Data source |
|------|--------------|-------------|
| Eval matrix | Per-sample × per-model pass/fail heatmap | `public/data.json` |
| Compare models | Grouped bar chart + model cards with score rings, per-format breakdown | `public/data.json` |
| Gap analysis | Leaderboard, head-to-head selector, per-format tables, confusion matrices | `public/gap_analysis_data.json` |
| Answers | Full sample table with gold vs each model's prediction, format filter | `public/data.json` |
| Live runs | Completed run list with actual correct/total from real records; click for sample log | `public/data.json` |
| Trust & reasoning | Trace faithfulness, gene verification, keyword consistency with interactive detail | `public/trace_faithfulness_scores.json` |
| Tasks | Task groups derived from loaded records, model summary table | `public/data.json` |
| Models | Per-model cards with real format scores, correct/total, avg latency | `public/data.json` |
| Senescence | Task A prompt browser: train/test split, format filter, search, expandable rows | `public/task_a_data.json` |
| Lipidomics | Task B prompt browser: train/test split, format filter, search, expandable rows | `public/task_b_data.json` |

Task switcher (top bar) lets you filter all Evaluate views to a single task group. Hidden on Senescence/Lipidomics library pages.

---

## Architecture

```
Task A parquet  ─┐
Task B parquet  ─┤
                 ↓
         run_inspect.py
              ├── parquet_task (@task)        reads parquet, builds ChatML samples
              ├── litellm_solver              calls L-LLM / Claude / baselines via LiteLLM
              └── longebench_scorer           format-aware: mcq/binary/pairwise/regression
                 ↓
         outputs/inspect/<model_name>/*.eval  (Inspect AI binary logs)
                 ↓
         tools/export_inspect_logs.py
                 ↓
         public/data.json                     {runs, samples, models, tasks}
                 ↓
         ┌───────────────────────────────────────┐
         │  src/analysis/gap_analysis.py         │
         │  → public/gap_analysis_data.json      │
         └───────────────────────────────────────┘
         ┌───────────────────────────────────────┐
         │  src/trace_scorer/trace_scorer.py     │
         │     entity_extractor.py               │
         │     verifiers/mygene_verifier.py      │  → mygene.info API
         │     consistency_checker.py            │  → keyword matching V4
         │  → public/trace_faithfulness_scores.json │
         └───────────────────────────────────────┘
                 ↓
         Dashboard (static React, no backend, no build step)
              index.html  loads all JSX via Babel standalone
              public/*.json  served by python3 -m http.server
```

---

## Task A — Senescence Perturbation

298 prompts across three formats derived from the Senescent Fibroblast Transcriptome Compendium filtered through CellAge v3.

| Format | N | Task | Gold | Metric |
|--------|---|------|------|--------|
| MCQ | 99 | Given experiment metadata, predict direction of gene expression change | A / B / C | Balanced accuracy |
| Binary | 100 | Predict whether perturbation produces a significant change (|LogFC| > 1.0, p < 0.05) | A / B | Balanced accuracy |
| Pairwise | 99 | Given two genes from same experiment, predict which shows larger |LogFC| | A / B | Accuracy |

Train/test split by GEO accession — 239 train / 59 test, 15 train accessions / 28 test accessions. Zero leaked treatments.

### Regenerate prompts

Download `Total_Data.csv` from https://research.ncl.ac.uk/cellularsenescence/downloadingdata/ and `cellage3.tsv` from https://genomics.senescence.info/cells/ into `data/task_a_senescence/raw/`.

```bash
cd data/task_a_senescence
python senescence_benchmark_pipeline.py \
  --dataset raw/Total_Data.csv \
  --cellage raw/cellage3.tsv \
  --output-dir processed
```

Outputs: `processed/task_a_senescence_{train,test}.parquet`, `…_{train,test}.json`, `task_a_senescence_summary.json`, `task_a_senescence_test_30.parquet` (10/format thinking-trace subset).

---

## Task B — Lipidomics

285 prompts across three formats derived from MTBLS4461 plasma lipidomics (1,864 donors × ~497 lipid features after gender balancing).

| Format | N | Task | Gold | Metric |
|--------|---|------|------|--------|
| MCQ | 85 | Predict age bracket from lipid profile (A=20–39 / B=40–59 / C=60–79 / D=80+) | A / B / C / D | Accuracy |
| Regression | 100 | Predict numeric age in years from lipid profile + diabetes status | integer years | MAE |
| Binary | 100 | Predict diabetes status (A=Yes / B=No) from lipid profile + age | A / B | Balanced accuracy |

Train/test: stratified by format, grouped by `individual_id` — 228 train / 57 test. No donor appears in both splits.

### Regenerate prompts

Download from [EBI MetaboLights MTBLS4461](https://www.ebi.ac.uk/metabolights/editor/MTBLS4461/samples) into `data/task_b_lipidomics/raw/`.

```bash
cd data/task_b_lipidomics

# 1. Join MAF abundance × sample metadata
python combine_lipidomics.py \
  --maf    raw/m_MTBLS4461_DI-MS_alternating__metabolite_profiling_v2_maf.tsv \
  --sample raw/s_MTBLS4461.txt \
  --out    combined_lipidomics.tsv

# 2. Gender balance (undersample males to female count, stratified on diabetes)
python balance_gender.py

# 3. Generate prompts + train/test split
python lipidomics_pipeline.py \
  --input balanced_lipidomics.tsv \
  --output-dir . \
  --target-per-task 50
```

Outputs: `task_b_lipidomics_{train,test}.parquet`, `…_{train,test}.json`, `task_b_lipidomics_summary.json`.

---

## Trace faithfulness scorer (V4)

Scores L-LLM thinking traces for biological grounding. Two components:

**Gene score** — extracts human/mouse gene symbols from trace via regex, verifies against mygene.info API (human/mouse/rat/fly/nematode/yeast namespaces). Cached in `outputs/mygene_cache.json`.

**Keyword consistency** — detects whether trace direction language (up/down/no-change keywords with negation detection) matches the predicted answer label. Returns 0.5 for pairwise/regression (no directional semantics).

```
faithfulness = 0.60 × gene_score + 0.40 × keyword_consistency
```

Replaces V3 (DeBERTa NLI) which gave 3.4% consistency — biological traces too long for 1024-token truncation. V4 keyword matching gives 24.1% consistency on same data.

```bash
# Run scorer
.venv/bin/python -m src.trace_scorer.trace_scorer

# Validate consistency checker
.venv/bin/python -m src.trace_scorer.validate
```

---

## Scoring criteria

| Criterion | Points | How we hit it |
|-----------|--------|---------------|
| Utility | 5 | Tasks target failure modes that break real research workflows |
| Diversity | 5 | Both tasks cover binary, MCQ, regression, and pairwise formats |
| Retrieval resistance | 5 | All questions derived from raw GEO/MetaboLights records, not paper text |
| Statistical rigor | 5 | Macro F1 + balanced accuracy + MAE + bootstrap CIs + baselines |

**Total: 20 points.**

---

## Key decisions

| Decision | Rationale |
|----------|-----------|
| Train/test split for Task A by GEO accession | Comparisons within a study share protocols and batch effects — random split leaks |
| Task A replaces Log2FC regression with binary significance | Regression on Log2FC was retrieval-vulnerable; binary "significant change?" is harder |
| Task B MCQ uses 4 brackets (20-39/40-59/60-79/80+) | Exposes high-age failure modes; 80+ bracket caps MCQ at 40 prompts |
| Task B replaces Pairwise with Binary diabetes | More clinically meaningful; exercises second label dimension already in MTBLS4461 |
| Keyword consistency (V4) replaces DeBERTa NLI (V3) | DeBERTa truncated at 1024 chars → missed biological conclusions; keywords work on full trace |
| Regression score = 1/(1+MAE) | Converts MAE to 0–1 ascending scale for unified dashboard display |
| Report macro F1 + balanced accuracy (not plain accuracy) | Class imbalance in all tasks makes plain accuracy misleading |
