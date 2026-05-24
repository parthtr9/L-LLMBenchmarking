# L-LLMBenchmarking

Caltech Longevity Hackathon Track 01 — LongevityLLM Benchmarking.
Evaluates L-LLM (Insilico Medicine) against Gemini, DeepSeek, Anthropic, and baselines on LongeBench and custom SynergyAge/MGI tasks.

**Stack:** Inspect AI (task orchestration + logs) · LiteLLM (provider abstraction) · HuggingFace datasets

---

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Fill in .env — see Required env vars below
```

---

## Required env vars

| Var | Required | Notes |
|-----|----------|-------|
| `HF_TOKEN` | Yes | Token needs **"Read access to public gated repositories"** enabled at huggingface.co/settings/tokens |
| `HF_ENDPOINT_URL` | Yes for L-LLM | Hosted vLLM endpoint from organizers |
| `GEMINI_API_KEY` | For gemini_flash | Google AI Studio key |
| `DEEPSEEK_API_KEY` | For deepseek_chat | DeepSeek platform key |
| `ANTHROPIC_API_KEY` | For claude_sonnet | Anthropic Console key |
| `OPENAI_API_KEY` | Optional | Only needed for direct OpenAI calls |

Never commit `.env`.

---

## Run one LongeBench task (Inspect AI — main orchestrator)

```bash
# Single model, 20 rows
.venv/bin/python -m src.eval.run_inspect \
  --lb-id LB-0038 \
  --limit 20 \
  --models longevity_llm

# Dry run — loads dataset, builds samples, skips all model calls
.venv/bin/python -m src.eval.run_inspect \
  --lb-id LB-0038 \
  --limit 3 \
  --models longevity_llm \
  --dry-run
```

---

## Run multiple providers in one command

```bash
.venv/bin/python -m src.eval.run_inspect \
  --lb-id LB-0038 \
  --limit 20 \
  --models longevity_llm,gemini_flash,deepseek_chat,claude_sonnet,random_baseline,majority_baseline
```

Each model gets its own subdirectory under `outputs/inspect/<model_name>/`.

---

## Model registry

Models are defined in [config/models.yaml](config/models.yaml). Add new providers there without touching Python code.

```yaml
my_new_model:
  litellm_model: "openai/my-model"
  api_base_env: "MY_ENDPOINT_URL"
  api_key_env: "MY_API_KEY"
```

Available out of the box: `longevity_llm`, `longevity_llm_thinking`, `gemini_flash`, `deepseek_chat`, `claude_sonnet`, `random_baseline`, `majority_baseline`.

---

## Open Inspect log viewer

```bash
inspect view outputs/inspect
# or a specific model's logs:
inspect view outputs/inspect/longevity_llm
```

Logs include raw response, parsed answer, gold answer, usage, latency, and score per sample.

---

## Automated pipeline (recommended)

[`pipeline.py`](pipeline.py) runs the full eval → export → dashboard flow interactively. It prompts `y/n` at every major step so nothing runs without confirmation.

```bash
.venv/bin/python pipeline.py
```

**What it does, step by step:**

| Step | What happens | Prompt |
|------|-------------|--------|
| 1. Choose models | Numbered list of all models from `config/models.yaml`. Enter numbers or names comma-separated. Default: `longevity_llm,majority_baseline,random_baseline` | input |
| 2. Choose task | Pick LB-ID from list (LB-0038 … LB-0090). Enter sample limit or press Enter for 50. | input |
| 3. Run eval | Shows full config summary, then runs `src.eval.run_inspect`. Live output streams to terminal. If eval errors, asks whether to continue to export anyway. | `y/n` |
| 4. Export | Runs `tools.export_inspect_logs` — writes `public/data.json` from all `.eval` logs under `outputs/inspect/`. | `y/n` |
| 5. Serve dashboard | Optionally starts `python3 -m http.server 8765` from the dashboard directory. Blocks until Ctrl-C. If declined, prints the manual command. | `y/n` |

**Example session:**

```
  LongevityBench Pipeline
  eval → export → dashboard

── STEP 1 — Choose models to evaluate ──────────────
   1) longevity_llm        (openai/longevity-llm)
   2) gemini_flash         (gemini/gemini-3.5-flash)
   3) claude_sonnet        (anthropic/claude-sonnet-4-6)
   4) random_baseline      (baseline:random)  [baseline]
   5) majority_baseline    (baseline:majority) [baseline]

  models: 1,3,4,5

── STEP 2 — Choose task and sample limit ───────────
  Task: LB-0038  |  Limit: 50

── STEP 3 — Run evaluation ─────────────────────────
  Run eval now? [y/n]: y
  ...live inspect output...

── STEP 4 — Export logs → dashboard JSON ───────────
  Export now? [y/n]: y
  wrote 50 samples, 2 runs across 4 models → public/data.json

── STEP 5 — Serve dashboard ────────────────────────
  Start HTTP server now? [y/n]: y
  Server starting on http://localhost:8765/
```

**Notes:**
- Run from repo root with the `.venv` Python.
- All env vars are loaded from `.env` automatically.
- The pipeline skips steps you decline — e.g. say `n` to serve if you already have a server running.
- Concurrency per model is controlled by `max_concurrency` in `config/models.yaml`. Gemini free tier is set to 2; Anthropic to 4; L-LLM to 8.

---

## Dashboard (static React UI)

Full pipeline: run eval → export → open browser.

```bash
# 1. Run eval (produces outputs/inspect/<model>/*.eval)
.venv/bin/python -m src.eval.run_inspect \
  --lb-id LB-0038 \
  --limit 50 \
  --models longevity_llm,majority_baseline,random_baseline

# 2. Export logs → dashboard JSON
.venv/bin/python -m tools.export_inspect_logs \
  --log-dir outputs/inspect \
  --out "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"

# 3. Serve dashboard (must serve from this exact directory)
cd "LongevityBench Design System/ui_kits/longevity_bench"
python3 -m http.server 8765
# open http://localhost:8765/
```

The dashboard loads `public/data.json` on page load — no backend needed. It is read-only; it never touches Inspect AI internals.

**Important:** serve from `LongevityBench Design System/ui_kits/longevity_bench/`, not a parent directory. The CSS design tokens (`design-tokens.css`) and data file (`public/data.json`) are resolved relative to that root.

---

## Fallback smoke runner (legacy)

The original `longebench_runner.py` calls the HF endpoint directly via the OpenAI SDK and is kept as a quick smoke-test tool:

```bash
.venv/bin/python -m src.eval.longebench_runner \
  --lb-id LB-0038 \
  --limit 20 \
  --concurrency 4 \
  --output outputs/lb0038_records.jsonl \
  --summary-output outputs/lb0038_summary.json

# Dry run / no model calls
.venv/bin/python -m src.eval.longebench_runner --dry-run --limit 3
```

Keep `--concurrency` ≤ 8 (shared endpoint).

---

## HuggingFace gated dataset notes

`insilicomedicine/longebench` is a gated repository. Two steps required:

1. Accept dataset terms at `huggingface.co/datasets/insilicomedicine/longebench`
2. Edit your token at `huggingface.co/settings/tokens` → enable **"Read access to public gated repositories"**

Classic "read" tokens include this permission by default. Fine-grained tokens require explicit opt-in.

---

## Pipeline architecture

```
run_inspect.py  →  longebench_task (@task)
                       ├── _load_hf_samples()       # HF datasets
                       ├── litellm_solver (@solver)  # LiteLLM → any provider
                       └── longebench_scorer (@scorer)  # format-aware

litellm_client.py   async acomplete()  →  litellm.acompletion()
                                              ├── openai/longevity-llm  (HF vLLM)
                                              ├── gemini/gemini-2.0-flash
                                              ├── deepseek/deepseek-chat
                                              └── anthropic/claude-sonnet-4-5
```

Scorers: regression MAE · MCQ letter extraction · set Jaccard · normalized exact match.

## Generating + Using Task A (Senescence)

### Prompt Generation
1. Download `Total_Data.csv` from https://research.ncl.ac.uk/cellularsenescence/downloadingdata/ to `data/task_a_senescence/raw/`. 
2. `cd data/task_a_senescence`
```bash
python senescence_benchmark_pipeline.py \
    --dataset raw/Total_Data.csv \
    --cellage raw/cellage3.tsv \
  --output-dir processed > processed/task_a_senescence_stdout.txt
```

### Usage

Prompts are stored in parquet file and have the same tabular format as LongevityBench tasks (see https://huggingface.co/datasets/insilicomedicine/longebench).

Prompts are split into 80-20 train-test split. 