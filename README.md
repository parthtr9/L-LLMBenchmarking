# LongevityBench-X

**Caltech Longevity Hackathon — Track 01: LongevityLLM Benchmarking**  
Sponsored by Insilico Medicine · Prize: $1,000 + co-authorship

Structured evaluation of L-LLM (Insilico Medicine's fine-tuned Qwen3.5-9B) against Claude Sonnet 4.6 across two novel biology benchmark tasks: senescence perturbation transcriptomics and plasma lipidomics. Includes an automated reasoning-trace faithfulness scorer and a static React dashboard for interactive result exploration.

---

## Submission files (JSONL — ChatML format)

All benchmark prompts are delivered as JSONL files. Each line is a JSON object with a `messages` array in OpenAI ChatML format (system → user → assistant). The `assistant` turn is the gold label.

| File | Task | Prompts |
|------|------|---------|
| `data/task_a_senescence/processed/task_a_senescence_train.json` | Senescence — train | 239 |
| `data/task_a_senescence/processed/task_a_senescence_test.json` | Senescence — test | 59 |
| `data/task_b_lipidomics/task_b_lipidomics_train.json` | Lipidomics — train | 228 |
| `data/task_b_lipidomics/task_b_lipidomics_test.json` | Lipidomics — test | 57 |

**One line, expanded:**

```json
{
  "lb_id": "LB-SEN-MCQ-0001",
  "pool": "senescence_perturbation_mcq",
  "display_group": "Senescence Perturbation",
  "domain": "transcriptomics",
  "format": "mcq",
  "metric": "accuracy",
  "messages": [
    {
      "role": "system",
      "content": "You are an expert computational biologist specializing in cellular senescence and transcriptomics. Answer concisely with only the letter of the correct option."
    },
    {
      "role": "user",
      "content": "<question>\nYou are presented with a senescence perturbation experiment...\n</question>\n<options>\nA. increases (upregulated)  B. decreases (downregulated)  C. no significant change\n</options>\n<experiment>\nCell line: IMR-90. Senescence model: OIS (RAS). Perturbation: knockdown of ITCH.\n</experiment>"
    },
    {
      "role": "assistant",
      "content": "C"
    }
  ],
  "has_reasoning": false,
  "metadata": "{\"follow_up\": \"Gene: IGFBP7. Log2FC=-0.78, p=0.019. GEO: GSE101766.\"}"
}
```

---

## What we built

| Task | Domain | Prompts | Formats | Test split |
|------|--------|---------|---------|------------|
| **Task A — Senescence Perturbation** | Transcriptomics | 298 | MCQ · Binary · Pairwise | 59 (by GEO accession) |
| **Task B — Lipidomics** | Lipidomics | 285 | MCQ · Binary · Regression | 57 (by donor ID) |

**Models evaluated:**

| Key | Model |
|-----|-------|
| `longevity_llm` | Qwen3.5-9B (L-LLM, thinking off) |
| `longevity_llm_thinking` | Qwen3.5-9B (L-LLM, thinking on, 3000 tokens) |
| `claude_sonnet` | Claude Sonnet 4.6 |
| `majority_baseline` | Majority label (from training distribution) |
| `random_baseline` | Uniform random draw |
| `population_prior_baseline` | US Census 2025 age distribution (Task B regression) |

**Stack:** Python 3.11 · Inspect AI · LiteLLM · mygene.info · Static React (no build step)

---

## Quickstart — view results (no API keys needed)

Pre-computed eval results, gap analysis, and trace faithfulness scores are included in the repo. To explore them:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then serve the dashboard:

```bash
cd "LongevityBench Design System/ui_kits/longevity_bench"
python3 -m http.server 8765
```

Open `http://localhost:8765/`. All data loads from static JSON files in `public/` — no backend, no API keys.

---

## Quickstart — reproduce evals from scratch

### 1. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env
```

| Variable | Required for | Where to get |
|----------|-------------|--------------|
| `HF_TOKEN` | L-LLM | huggingface.co/settings/tokens |
| `HF_ENDPOINT_URL` | L-LLM | vLLM-compatible endpoint from hackathon organizers |
| `ANTHROPIC_API_KEY` | Claude Sonnet | console.anthropic.com |

Never commit `.env`.

### 3. Run the pipeline

```bash
caffeinate -i .venv/bin/python pipeline.py
```

`caffeinate -i` prevents sleep during long eval runs. The pipeline walks through 7 interactive steps.

---

## Pipeline steps

```
Step 1    Choose models to evaluate
Step 2    Choose dataset (test / train / single task)
Step 3    Run evaluation (Inspect AI) ← API calls happen here
Step 4    Cache predictions           ← auto
Step 5    Export logs → data.json     ← auto
Step 5.5  Export task browser JSON    ← auto
Step 6    Gap analysis
Step 6.5  Trace faithfulness scoring
Step 7    Serve dashboard
```

For a full run (6 models × 2 tasks × ~250 samples each): expect 30–90 minutes depending on endpoint speed.

---

## Run steps manually

```bash
# Eval — Task A, all models, test set
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test.parquet \
  --models longevity_llm,claude_sonnet,majority_baseline,random_baseline

# Eval — Task B, test set
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_b_lipidomics/task_b_lipidomics_test.parquet \
  --models longevity_llm,claude_sonnet,majority_baseline,random_baseline,population_prior_baseline

# Export logs → dashboard JSON
.venv/bin/python -m tools.export_inspect_logs \
  --log-dir outputs/inspect \
  --out "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"

# Gap analysis
.venv/bin/python -m src.analysis.gap_analysis

# Trace faithfulness scorer
.venv/bin/python -m src.trace_scorer.trace_scorer

# Serve dashboard
cd "LongevityBench Design System/ui_kits/longevity_bench"
python3 -m http.server 8765
```

---

## Benchmark tasks

### Task A — Senescence Perturbation

Derived from the Senescent Fibroblast Transcriptome Compendium (119 studies, 1,069 comparisons) cross-referenced against CellAge v3 senescence gene database. All questions ask about the transcriptomic effect of a perturbation (knockdown / overexpression / drug) applied on top of a senescent baseline.

| Format | N | Question | Gold | Metric |
|--------|---|----------|------|--------|
| MCQ | 99 | Predict expression direction given experiment metadata | A=up / B=down / C=no change | `accuracy` (33/33/33 balanced) |
| Binary | 100 | Predict whether perturbation produces significant change (\|LogFC\| > 1.0, p < 0.05) | A=significant / B=not | `accuracy` (50/50 balanced) |
| Pairwise | 99 | Given two genes from same experiment, predict which shows larger \|LogFC\| | A or B | `balanced_accuracy` |

**Train/test split:** by GEO accession — 239 train / 59 test, 15 train accessions / 28 test accessions. Zero treatment leakage between splits.

**Regenerate prompts:**

Download `Total_Data.csv` from [Cellular Senescence downloads](https://research.ncl.ac.uk/cellularsenescence/downloadingdata/) and `cellage3.tsv` from [genomics.senescence.info](https://genomics.senescence.info/cells/) into `data/task_a_senescence/raw/`, then:

```bash
cd data/task_a_senescence
python senescence_benchmark_pipeline.py \
  --dataset raw/Total_Data.csv \
  --cellage raw/cellage3.tsv \
  --output-dir processed
```

---

### Task B — Lipidomics

Derived from MTBLS4461 plasma lipidomics (DI-MS alternating polarity, EBI MetaboLights). 1,864 donors × ~497 lipid features after gender balancing and diabetes-NaN removal.

| Format | N | Question | Gold | Metric |
|--------|---|----------|------|--------|
| MCQ | 85 | Predict age bracket from lipid profile | A=20–39 / B=40–59 / C=60–79 / D=80+ | `off_by_one_accuracy` (1.0 exact, 0.5 adjacent) |
| Regression | 100 | Predict numeric age in years (lipid profile + diabetes status) | integer years | `mae` |
| Binary | 100 | Predict diabetes status (lipid profile + age) | A=Yes / B=No | `accuracy` |

**Train/test split:** stratified by format, grouped by `individual_id` — 228 train / 57 test. No donor appears in both splits.

**Regenerate prompts:**

Download from [EBI MetaboLights MTBLS4461](https://www.ebi.ac.uk/metabolights/editor/MTBLS4461/samples) into `data/task_b_lipidomics/raw/`, then:

```bash
cd data/task_b_lipidomics
python combine_lipidomics.py \
  --maf    raw/m_MTBLS4461_DI-MS_alternating__metabolite_profiling_v2_maf.tsv \
  --sample raw/s_MTBLS4461.txt \
  --out    combined_lipidomics.tsv
python balance_gender.py
python lipidomics_pipeline.py --input balanced_lipidomics.tsv --output-dir . --target-per-task 100
```

---

## Reasoning trace scorer (V5)

Scores L-LLM thinking traces for biological grounding. Applied to `longevity_llm_thinking` outputs only.

```
faithfulness = 0.40 × gene_score
             + 0.20 × keyword_consistency
             + 0.40 × property_score
```

| Component | Method |
|-----------|--------|
| **Gene score** | mygene.info batch lookup · 6 species · verifies gene symbols exist |
| **Keyword consistency** | Directional keyword scan (up/down + negation detection) vs predicted label |
| **Property score** | CellAge v3 (949 genes) · checks directional claims in trace against annotated Induces/Inhibits effect |

Replaces V3 DeBERTa NLI (3.4% consistency due to 1024-token truncation). V5 keyword + CellAge grounding on the full trace gives ~24% directional consistency with falsifiable, database-anchored violations.

---

## Dashboard pages

Served from `http://localhost:8765/`. All views read static JSON — no backend.

| Page | What it shows |
|------|--------------|
| **Eval Matrix** | Per-sample × per-model pass/fail heatmap |
| **Compare** | Grouped bar chart, model cards, per-format breakdown |
| **Answers** | Gold answer vs each model's prediction |
| **Gap Analysis** | Leaderboard, head-to-head, confusion matrices, distribution bars |
| **Live Runs** | Completed run list, click for sample log |
| **Trust & Reasoning** | Trace faithfulness, gene verification, keyword consistency |
| **Senescence** | Task A prompt browser: train/test split, format filter, search |
| **Lipidomics** | Task B prompt browser: train/test split, format filter, search |

---

## Scoring criteria

| Criterion | Points | How we hit it |
|-----------|--------|---------------|
| Utility | 5 | Tasks target failure modes that break real research workflows |
| Diversity | 5 | Both tasks cover MCQ, binary, pairwise, and regression formats |
| Retrieval resistance | 5 | All questions derived from raw GEO / MetaboLights records, not paper text |
| Statistical rigor | 5 | Macro F1 + balanced accuracy + off-by-one accuracy + MAE + bootstrap CIs + baselines |

Always report majority-class baseline alongside model scores.

---

## Repository structure

```
L-LLMBenchmarking/
├── pipeline.py                          ← main entry point
├── config/models.yaml                   ← model registry (add providers without touching Python)
├── .env.example                         ← copy to .env, fill in keys
├── requirements.txt
│
├── data/
│   ├── task_a_senescence/
│   │   ├── raw/                         ← Total_Data.csv, cellage3.tsv
│   │   ├── processed/                   ← train/test parquets + JSONL ← SUBMISSION FILES
│   │   └── senescence_benchmark_pipeline.py
│   └── task_b_lipidomics/
│       ├── raw/                         ← MTBLS4461 MAF + sample sheet
│       ├── task_b_lipidomics_{train,test}.parquet
│       ├── task_b_lipidomics_{train,test}.json  ← SUBMISSION FILES
│       ├── combine_lipidomics.py
│       ├── balance_gender.py
│       └── lipidomics_pipeline.py
│
├── src/
│   ├── eval/
│   │   ├── run_inspect.py               ← CLI: --parquet, --models, --max-tokens
│   │   ├── inspect_solvers.py           ← litellm_solver + baseline solvers
│   │   ├── inspect_scorers.py           ← accuracy / balanced_accuracy / off_by_one / mae
│   │   └── inspect_tasks/parquet_task.py
│   ├── trace_scorer/
│   │   ├── trace_scorer.py              ← V5 orchestrator
│   │   ├── entity_extractor.py          ← multi-species gene regex
│   │   ├── consistency_checker.py       ← keyword matching + negation detection
│   │   ├── property_checker.py          ← CellAge v3 directional claim check
│   │   └── verifiers/mygene_verifier.py ← mygene.info API (cached)
│   └── analysis/gap_analysis.py
│
├── tools/
│   ├── export_inspect_logs.py           ← .eval logs → public/data.json
│   ├── export_task_data.py              ← parquets → public/task_{a,b}_data.json
│   └── cache_predictions.py
│
├── outputs/
│   ├── inspect/                         ← .eval logs per model
│   ├── gap_analysis_report.md
│   └── mygene_cache.json
│
└── LongevityBench Design System/
    └── ui_kits/longevity_bench/
        ├── index.html                   ← dashboard (open after http.server)
        ├── public/
        │   ├── data.json
        │   ├── gap_analysis_data.json
        │   ├── trace_faithfulness_scores.json
        │   ├── task_a_data.json
        │   └── task_b_data.json
        └── *.jsx                        ← React components (Babel, no build step)
```

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| Train/test split for Task A by GEO accession | Comparisons within a study share protocols and batch effects — random split leaks |
| Task A binary significance instead of Log2FC regression | Regression on Log2FC is retrieval-vulnerable; "significant change?" is a harder, cleaner task |
| Task B MCQ uses 4 age brackets with off-by-one scoring | Age brackets are ordinal — adjacent predictions should not be penalized equally to wildly wrong ones |
| Task B binary diabetes instead of pairwise | More clinically meaningful; exercises a second label dimension already in MTBLS4461 |
| V5 keyword + CellAge replaces DeBERTa NLI | DeBERTa truncates at 1024 tokens, missing biological conclusions in long traces |
| Regression displayed as 1/(1+MAE) in dashboard | Converts MAE to 0–1 ascending scale for unified display alongside accuracy metrics |
| Majority baseline computed from training targets | Correct evaluation protocol — test labels never seen at baseline-fitting time |
