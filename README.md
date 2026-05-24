# LongevityBench-X

**Caltech Longevity Hackathon — Track 01: LongevityLLM Benchmarking**
Sponsored by Insilico Medicine · Prize: $1,000 + co-authorship

Evaluates L-LLM (Insilico Medicine's fine-tuned Qwen3.5-9B) against Claude Sonnet 4.6 and baselines across two novel biology benchmark tasks. Includes an automated reasoning-trace faithfulness scorer and a static React dashboard for interactive result exploration.

---

## What we built

| Task | Prompts | Formats | Domain |
|------|---------|---------|--------|
| **Task A — Senescence Perturbation** | 298 | MCQ · Binary · Pairwise | Transcriptomics |
| **Task B — Lipidomics** | 285 | MCQ · Binary · Regression | Lipidomics |

**Six models evaluated:**

| Key | Model | Notes |
|-----|-------|-------|
| `longevity_llm` | Qwen3.5-9B (L-LLM) | Insilico Medicine fine-tune, thinking off |
| `longevity_llm_thinking` | Qwen3.5-9B (L-LLM) | Thinking on, max 3000 tokens |
| `claude_sonnet` | Claude Sonnet 4.6 | Via Anthropic API |
| `majority_baseline` | Majority label | Computed from training distribution |
| `random_baseline` | Random label | Uniform draw over valid label set |
| `population_prior_baseline` | Census-weighted age | US Census 2025 age distribution (Task B regression) |

**Stack:** Python 3.11 · Inspect AI · LiteLLM · mygene.info · Static React (no build step)

---

## Quick start

### 1. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env and fill in your keys
```

| Variable | Required for | Where to get |
|----------|-------------|--------------|
| `HF_TOKEN` | L-LLM | huggingface.co/settings/tokens (classic read token) |
| `HF_ENDPOINT_URL` | L-LLM | vLLM-compatible endpoint from hackathon organizers |
| `ANTHROPIC_API_KEY` | Claude Sonnet | console.anthropic.com |

Never commit `.env`.

### 3. Run the pipeline

```bash
caffeinate -i .venv/bin/python pipeline.py
```

`caffeinate -i` prevents laptop sleep during long evals. The pipeline walks you through every step interactively.

---

## Pipeline walkthrough

Running `pipeline.py` presents 7 interactive steps. Steps 4, 5, and 5.5 run automatically without prompts.

```
Step 1  Choose models to evaluate
Step 2  Choose dataset (test / train / single task)
Step 3  Run evaluation (Inspect AI)      ← API calls happen here
Step 4  Cache predictions                ← auto
Step 5  Export logs → data.json          ← auto
Step 5.5 Export task browser JSON        ← auto
Step 6  Gap analysis
Step 6.5 Trace faithfulness scoring
Step 7  Serve dashboard
```

### Step 1 — Choose models

Pick by number or comma-separated list. Default: `longevity_llm,majority_baseline,random_baseline`.

### Step 2 — Choose dataset

```
0  → all test sets   (Task A test 59 + Task B test 57)
t  → all train sets  (Task A train 225 + Task B train 228)
1  → task_a_senescence only
2  → task_b_lipidomics only
```

For single task you can also filter by format (mcq/binary/pairwise/regression) and set a sample limit.

### Step 3 — Evaluation

Runs Inspect AI with the selected models against the selected parquet(s). Logs saved to `outputs/inspect/<model_name>/`. For a full run (6 models × 2 tasks × ~250 samples each), expect 30–90 minutes depending on endpoint speed.

### Step 4 — Cache predictions (auto)

Reads all `.eval` logs and writes `outputs/prediction_cache.json` keyed `model_name::lb_id`. Re-runs skip cached samples — no duplicate API calls.

### Step 5 — Export logs (auto)

Converts `.eval` binary logs to `public/data.json`. This feeds all dashboard views.

### Step 5.5 — Export task browser JSON (auto)

Writes `public/task_a_data.json` and `public/task_b_data.json` for the Senescence and Lipidomics prompt-browser pages.

### Step 6 — Gap analysis

Reads `public/data.json`. Writes:
- `outputs/gap_analysis_report.md` — human-readable findings
- `public/gap_analysis_data.json` — structured JSON for dashboard Gap Analysis view

### Step 6.5 — Trace faithfulness scoring

Two sub-steps (each asks for confirmation):

1. **V5 scorer** — keyword matching + mygene.info gene verification. Fast, no API cost.
2. **Claude oracle** — Claude Sonnet verifies biological claims in traces. Costs API credits.

Writes `public/trace_faithfulness_scores.json` for the Trust & Reasoning dashboard page.

### Step 7 — Serve dashboard

```
http://localhost:8765/
```

Must serve from `LongevityBench Design System/ui_kits/longevity_bench/` — CSS tokens and JSON files resolve relative to that directory.

---

## Run evals manually (without pipeline)

```bash
# Task A — all 6 models, test set
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test.parquet \
  --models longevity_llm,longevity_llm_thinking,claude_sonnet,majority_baseline,random_baseline,population_prior_baseline

# Task B — test set
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_b_lipidomics/task_b_lipidomics_test.parquet \
  --models longevity_llm,claude_sonnet,majority_baseline,random_baseline,population_prior_baseline

# Single format, sample limit
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test.parquet \
  --models longevity_llm \
  --fmt-filter mcq \
  --limit 10
```

`--max-tokens` defaults to 500; override for thinking models with `--max-tokens 3000` (or it's read automatically from `config/models.yaml`).

---

## Run individual pipeline steps manually

```bash
# Export .eval logs → data.json
.venv/bin/python -m tools.export_inspect_logs \
  --log-dir outputs/inspect \
  --out "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"

# Export task browser JSONs
.venv/bin/python -m tools.export_task_data

# Cache predictions
.venv/bin/python tools/cache_predictions.py

# Gap analysis
.venv/bin/python -m src.analysis.gap_analysis

# Trace faithfulness scorer
.venv/bin/python -m src.trace_scorer.trace_scorer

# Serve dashboard
cd "LongevityBench Design System/ui_kits/longevity_bench"
python3 -m http.server 8765
```

---

## Dashboard pages

Open `http://localhost:8765/` after running Step 7. All views pull from static JSON — no backend.

| Page | What it shows | Data source |
|------|--------------|-------------|
| **Eval Matrix** | Per-sample × per-model pass/fail heatmap | `data.json` |
| **Compare** | Grouped bar chart, model cards with score rings, per-format breakdown | `data.json` |
| **Answers** | Full sample table — gold answer vs each model's prediction | `data.json` |
| **Gap Analysis** | Leaderboard, head-to-head selector, confusion matrices, distribution bars | `gap_analysis_data.json` |
| **Live Runs** | Completed run list, click to drill into sample log | `data.json` |
| **Trust & Reasoning** | Trace faithfulness, gene verification, keyword consistency | `trace_faithfulness_scores.json` |
| **Tasks** | Task groups, model summary table | `data.json` |
| **Models** | Per-model cards: format scores, correct/total, avg latency | `data.json` |
| **Senescence** | Task A prompt browser: train/test split, format filter, search | `task_a_data.json` |
| **Lipidomics** | Task B prompt browser: train/test split, format filter, search | `task_b_data.json` |

---

## Benchmark tasks

### Task A — Senescence Perturbation

Derived from the Senescent Fibroblast Transcriptome Compendium (119 studies, 1,069 comparisons) filtered through CellAge v3. All questions involve predicting the transcriptomic effect of a perturbation (knockdown/overexpression/drug) on top of a senescent baseline.

| Format | N | Task | Gold | Metric |
|--------|---|------|------|--------|
| MCQ | 99 | Given experiment metadata, predict direction of expression change | A/B/C | `accuracy` (33/33/33 balanced) |
| Binary | 100 | Predict whether perturbation produces significant change (\|LogFC\| > 1.0, p < 0.05) | A/B | `accuracy` (50/50 balanced) |
| Pairwise | 99 | Given two genes from same experiment, predict which shows larger \|LogFC\| | A/B | `balanced_accuracy` |

**Train/test split:** by GEO accession — 225 train / 59 test. All prompts from one study go to the same split. Zero treatment leakage.

**lb_id prefixes:** `LB-SEN-MCQ`, `LB-SEN-PAIR`, `LB-SEN-SIG`

**Regenerate prompts:**

Download `Total_Data.csv` from [Cellular Senescence downloads](https://research.ncl.ac.uk/cellularsenescence/downloadingdata/) and `cellage3.tsv` from [genomics.senescence.info](https://genomics.senescence.info/cells/) into `data/task_a_senescence/raw/`.

```bash
cd data/task_a_senescence
python senescence_benchmark_pipeline.py \
  --dataset raw/Total_Data.csv \
  --cellage raw/cellage3.tsv \
  --output-dir processed
```

---

### Task B — Lipidomics

Derived from MTBLS4461 plasma lipidomics (DI-MS alternating polarity). 1,864 donors × ~497 lipid features after gender balancing and diabetes-NaN removal.

| Format | N | Task | Gold | Metric |
|--------|---|------|------|--------|
| MCQ | 85 | Predict age bracket from lipid profile | A=20–39 / B=40–59 / C=60–79 / D=80+ | `off_by_one_accuracy` (ordinal: 1.0 exact, 0.5 adjacent) |
| Regression | 100 | Predict numeric age in years (lipid profile + diabetes status) | integer years | `mae` |
| Binary | 100 | Predict diabetes status (lipid profile + age) | A=Yes / B=No | `accuracy` |

**Train/test split:** stratified by format, grouped by `individual_id` — 228 train / 57 test. No donor appears in both splits.

**lb_id prefixes:** `LB-LIP-MCQ`, `LB-LIP-REG`, `LB-LIP-DIAB`

**Regenerate prompts:**

Download from [EBI MetaboLights MTBLS4461](https://www.ebi.ac.uk/metabolights/editor/MTBLS4461/samples) into `data/task_b_lipidomics/raw/`.

```bash
cd data/task_b_lipidomics

python combine_lipidomics.py \
  --maf    raw/m_MTBLS4461_DI-MS_alternating__metabolite_profiling_v2_maf.tsv \
  --sample raw/s_MTBLS4461.txt \
  --out    combined_lipidomics.tsv

python balance_gender.py

python lipidomics_pipeline.py \
  --input balanced_lipidomics.tsv \
  --output-dir . \
  --target-per-task 100
```

---

## Trace faithfulness scorer

Scores L-LLM thinking traces for biological grounding. Applied to `longevity_llm_thinking` outputs only.

**Formula:**
```
faithfulness = 0.60 × gene_score + 0.40 × keyword_consistency
```

**Gene score** — extracts gene symbols from trace (regex, multi-species), verifies via mygene.info API. Cached in `outputs/mygene_cache.json`.

**Keyword consistency** — detects whether trace direction language (up/down + negation detection) matches the predicted label. Returns 0.5 for pairwise/regression (no directional semantics).

Replaces V3 (DeBERTa NLI) which gave 3.4% consistency because biological traces exceed the 1024-token DeBERTa limit. V4/V5 keyword matching on the full trace gives ~24% consistency on the same data.

---

## Model registry

All models defined in `config/models.yaml`. Add a new provider without touching Python — just add an entry and reference the API key env var.

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
    max_tokens: 3000

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

  population_prior_baseline:
    type: baseline
    strategy: population_prior
    csv_path: "data/task_b_lipidomics/nc-est2025-agesex-res.csv"
    year_col: "POPESTIMATE2025"
    age_min: 20
    age_max: 90
```

---

## Prompt format (JSONL / ChatML)

All benchmark prompts are stored as parquet with a `messages` column. JSONL export = one row per line in OpenAI ChatML format. Compatible with any OpenAI-API-compatible endpoint.

**One JSONL line:**
```json
{
  "lb_id": "LB-SEN-MCQ-0001",
  "format": "mcq",
  "metric": "accuracy",
  "domain": "transcriptomics",
  "messages": [
    {"role": "system",    "content": "You are an expert computational biologist..."},
    {"role": "user",      "content": "<question>...</question><options>A. ... B. ...</options>"},
    {"role": "assistant", "content": "B"}
  ]
}
```

The `assistant` turn is the gold label — what the model should predict.

**JSONL files** (already exported):
- `data/task_a_senescence/processed/task_a_senescence_test.json`
- `data/task_a_senescence/processed/task_a_senescence_train.json`
- `data/task_b_lipidomics/task_b_lipidomics_test.json`
- `data/task_b_lipidomics/task_b_lipidomics_train.json`

---

## Scoring criteria

| Criterion | Points | How we hit it |
|-----------|--------|---------------|
| Utility | 5 | Tasks target failure modes that break real research workflows |
| Diversity | 5 | Both tasks cover MCQ, binary, pairwise, and regression formats |
| Retrieval resistance | 5 | All questions derived from raw GEO/MetaboLights records, not paper text |
| Statistical rigor | 5 | Macro F1 + balanced accuracy + off-by-one accuracy + MAE + bootstrap CIs + baselines |

**Total: 20 points.**

Always report majority-class baseline F1 alongside model F1. A model scoring 0.62 F1 where majority-class gets 0.61 is not impressive.

---

## Repository structure

```
L-LLMBenchmarking/
├── pipeline.py                      ← main entry point — run this
├── config/
│   └── models.yaml                  ← model registry
├── .env.example                     ← copy to .env, fill in keys
├── requirements.txt
│
├── data/
│   ├── task_a_senescence/
│   │   ├── raw/                     ← Total_Data.csv, cellage3.tsv
│   │   ├── processed/               ← train/test parquets + JSONL
│   │   └── senescence_benchmark_pipeline.py
│   └── task_b_lipidomics/
│       ├── raw/                     ← MTBLS4461 MAF + sample sheet
│       ├── task_b_lipidomics_{train,test}.parquet
│       ├── task_b_lipidomics_{train,test}.json
│       ├── combine_lipidomics.py
│       ├── balance_gender.py
│       └── lipidomics_pipeline.py
│
├── src/
│   ├── eval/
│   │   ├── run_inspect.py           ← CLI: --parquet, --models, --max-tokens
│   │   ├── inspect_solvers.py       ← litellm_solver + baseline solvers
│   │   ├── inspect_scorers.py       ← accuracy / balanced_accuracy / off_by_one / mae
│   │   ├── inspect_tasks/
│   │   │   └── parquet_task.py      ← Inspect AI @task, builds ChatML samples
│   │   └── litellm_client.py        ← async LiteLLM wrapper with retry
│   ├── trace_scorer/
│   │   ├── trace_scorer.py          ← orchestrator: gene_score + keyword_consistency
│   │   ├── entity_extractor.py      ← regex gene extraction (multi-species)
│   │   ├── consistency_checker.py   ← V5 keyword matching with negation detection
│   │   └── verifiers/
│   │       └── mygene_verifier.py   ← mygene.info API (cached)
│   └── analysis/
│       └── gap_analysis.py          ← reads data.json → gap_analysis_data.json + report.md
│
├── tools/
│   ├── export_inspect_logs.py       ← .eval logs → public/data.json
│   ├── export_task_data.py          ← parquets → public/task_{a,b}_data.json
│   └── cache_predictions.py        ← .eval logs → outputs/prediction_cache.json
│
├── outputs/
│   ├── inspect/                     ← .eval logs per model
│   ├── prediction_cache.json        ← keyed model_name::lb_id
│   ├── mygene_cache.json
│   ├── gap_analysis_report.md
│   └── benchmark_card.md
│
└── LongevityBench Design System/
    └── ui_kits/longevity_bench/
        ├── index.html               ← dashboard entry point
        ├── public/
        │   ├── data.json
        │   ├── gap_analysis_data.json
        │   ├── trace_faithfulness_scores.json
        │   ├── task_a_data.json
        │   └── task_b_data.json
        └── *.jsx                    ← React components (Babel, no build step)
```

---

## Data flow

```
Task A parquet  ──┐
Task B parquet  ──┤
                  ↓
          run_inspect.py
               ├── parquet_task (@task)   reads parquet, builds ChatML samples
               ├── litellm_solver         calls LLMs / baselines via LiteLLM
               └── longebench_scorer      accuracy / balanced_accuracy / off_by_one / mae
                  ↓
          outputs/inspect/<model>/*.eval
                  ↓
          export_inspect_logs.py  →  public/data.json
          export_task_data.py     →  public/task_{a,b}_data.json
          cache_predictions.py    →  outputs/prediction_cache.json
                  ↓
          gap_analysis.py         →  public/gap_analysis_data.json
          trace_scorer.py         →  public/trace_faithfulness_scores.json
                  ↓
          Static React dashboard (python3 -m http.server 8765)
```

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| Train/test split for Task A by GEO accession | Comparisons within a study share protocols and batch effects — random split leaks |
| Task A uses binary significance instead of Log2FC regression | Regression on Log2FC is retrieval-vulnerable; "significant change?" is a harder, cleaner task |
| Task B MCQ uses 4 age brackets (20-39/40-59/60-79/80+) | Exposes high-age failure modes; off-by-one scoring credits ordinal proximity |
| Task B replaces pairwise with binary diabetes prediction | More clinically meaningful; exercises a second label dimension already in MTBLS4461 |
| Keyword consistency (V5) replaces DeBERTa NLI (V3) | DeBERTa truncates at 1024 tokens, missing biological conclusions in long traces |
| Regression displayed as 1/(1+MAE) in dashboard | Converts MAE to 0–1 ascending scale for unified display alongside accuracy metrics |
| Prediction cache keyed model_name::lb_id | Re-running evals after partial failures skips already-evaluated samples |
| Majority baseline computed from training targets | Correct evaluation protocol — test labels never seen at baseline-fitting time |
