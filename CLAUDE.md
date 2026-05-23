# CLAUDE.md — LongevityBench-X

Collaborative coding guide for the Caltech Longevity Hackathon, Track 01 · LongevityLLM Benchmarking.
Sponsored by Insilico Medicine. Prize: $1,000 + co-authorship on a peer-reviewed publication.

---

## What we are building

We are extending the LongevityBench framework with two novel benchmark task suites and an automated
reasoning-trace scorer. The end goal is a structured evaluation of L-LLM (Insilico Medicine's
fine-tuned Qwen3.5-9B) against GPT-4o, with a gap analysis report showing exactly where and why
L-LLM succeeds or fails compared to general-purpose models.

**Three deliverables:**

1. `task_a_synergyage/` — Gene-combination epistasis prediction benchmark (~200 prompts)
2. `task_b_mgi/` — Mouse allele → lifespan effect benchmark (~150 prompts)
3. `trace_scorer/` — Automated biological fact-checker for L-LLM reasoning traces (extra credit)

All benchmark tasks must be submitted as JSONL files in ChatML format (see spec below).

---

## Scoring criteria (judges use this — keep it visible)

| Criterion           | Points | How we hit it                                                   |
|---------------------|--------|-----------------------------------------------------------------|
| Utility             | 5      | Tasks target failure modes that break real research workflows   |
| Diversity           | 5      | Every task has binary, ternary, regression, and pairwise variants |
| Retrieval resistance| 5      | All questions derived from raw database records, not paper text |
| Statistical rigor   | 5      | Macro F1 + balanced accuracy + MAE + bootstrap CIs + baselines |

**Total: 20 points.** Do not sacrifice any criterion to speed up another.

---

## Repository structure

```
longevity-bench-x/
│
├── CLAUDE.md                        ← you are here
├── README.md                        ← human-readable project summary
├── requirements.txt
├── .env.example                     ← API keys go in .env (never commit .env)
│
├── data/
│   ├── raw/
│   │   ├── synergyage/              ← downloaded CSVs from synergyage.info
│   │   └── mgi/                     ← MGI_PhenoGenoMP.rpt and supporting files
│   └── processed/
│       ├── task_a_train.jsonl
│       ├── task_a_test.jsonl
│       ├── task_b_train.jsonl
│       └── task_b_test.jsonl
│
├── src/
│   ├── data_loaders/
│   │   ├── __init__.py
│   │   ├── synergyage_loader.py     ← parses SynergyAge CSVs into structured records
│   │   └── mgi_loader.py            ← parses MGI phenotype annotation file
│   │
│   ├── prompt_generators/
│   │   ├── __init__.py
│   │   ├── base_generator.py        ← abstract base class for all generators
│   │   ├── task_a_generator.py      ← SynergyAge → ChatML JSONL prompts
│   │   └── task_b_generator.py      ← MGI → ChatML JSONL prompts
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── runner.py                ← calls L-LLM and GPT-4o APIs, saves raw responses
│   │   ├── scorer.py                ← computes F1, balanced accuracy, MAE, bootstrap CIs
│   │   └── baseline.py              ← majority-class and random baselines
│   │
│   ├── trace_scorer/
│   │   ├── __init__.py
│   │   ├── entity_extractor.py      ← pulls gene symbols, pathways, strains from traces
│   │   ├── verifiers/
│   │   │   ├── ncbi_verifier.py     ← hits NCBI Gene eutils API
│   │   │   ├── kegg_verifier.py     ← hits KEGG REST API
│   │   │   ├── string_verifier.py   ← hits STRING-DB API for interaction claims
│   │   │   └── mgi_verifier.py      ← verifies murine strain/allele claims
│   │   ├── consistency_checker.py   ← compares trace direction with final answer label
│   │   └── trace_scorer.py          ← aggregates all verifier outputs into a 0–1 score
│   │
│   └── analysis/
│       ├── gap_analysis.py          ← compares L-LLM vs GPT-4o across task/format
│       └── report_generator.py      ← outputs markdown + CSV summary tables
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_prompt_inspection.ipynb
│   └── 03_results_analysis.ipynb
│
├── outputs/
│   ├── task_a_train.jsonl           ← final submission files
│   ├── task_a_test.jsonl
│   ├── task_b_train.jsonl
│   ├── task_b_test.jsonl
│   ├── results_task_a.json
│   ├── results_task_b.json
│   └── gap_analysis_report.md
│
└── tests/
    ├── test_loaders.py
    ├── test_generators.py
    └── test_trace_scorer.py
```

---

## Data sources

### Task A — SynergyAge

- **URL:** https://synergyage.info (download the full CSV export)
- **What it contains:** Multi-gene longevity intervention experiments across C. elegans,
  D. melanogaster, mice, and yeast. Each row = a genetic combination with lifespan % change.
- **Columns we care about:**
  - `gene_1`, `gene_2` (and `gene_3` if present) — intervention genes
  - `organism` — used for train/test split
  - `single_gene_1_lifespan_change_pct`, `single_gene_2_lifespan_change_pct`
  - `combined_lifespan_change_pct` — this is our regression target
  - `epistasis_type` — synergistic / antagonistic / additive — classification target
- **Train/test split:** by organism. Train on C. elegans + yeast. Test on D. melanogaster + mouse.
  Never split randomly — this leaks data.
- **Minimum N:** 200 prompts total. Filter to rows where `combined_lifespan_change_pct` is numeric.

### Task B — MGI Mouse Allele Phenotypes

- **URL:** https://www.informatics.jax.org/downloads/reports/index.html
- **File:** `MGI_PhenoGenoMP.rpt` — tab-separated, allele × phenotype annotations
- **Filtering logic:**
  - Keep rows where Mammalian Phenotype Ontology term is MP:0010765 (increased lifespan)
    or MP:0010767 (decreased lifespan)
  - Also capture MP:0002058 (normal lifespan) for the "no change" ternary class
- **Columns we care about:**
  - `allele_symbol`, `allele_name`, `allele_type` (e.g. targeted mutation, spontaneous)
  - `gene_symbol`, `gene_name`
  - `genetic_background` (e.g. C57BL/6J)
  - `phenotype_id`, `phenotype_label`
- **Train/test split:** by chromosome (pull from MGI gene coordinate data).
  Train: chromosomes 1–16. Test: chromosomes 17–19 + X.
- **Minimum N:** 150 prompts total.

---

## Prompt format (ChatML JSONL — required by judges)

Every prompt must be a JSON object on a single line with this exact structure:

```json
{
  "task_id": "synergyage_001",
  "task_name": "epistasis_ternary",
  "format": "ternary_classification",
  "split": "test",
  "messages": [
    {
      "role": "system",
      "content": "You are an expert in aging biology and longevity genetics. Answer concisely and precisely. Output only the requested label or value, with no explanation unless asked."
    },
    {
      "role": "user",
      "content": "<prompt text here>"
    }
  ],
  "ground_truth": "synergistic",
  "metadata": {
    "organism": "C. elegans",
    "gene_1": "daf-2",
    "gene_2": "age-1",
    "single_1_pct": -100.0,
    "single_2_pct": -100.0,
    "source_db": "SynergyAge",
    "source_id": "SYN-0042"
  }
}
```

**Required fields on every record:** `task_id`, `task_name`, `format`, `split`, `messages`,
`ground_truth`, `metadata.source_db`, `metadata.source_id`.

**Token limit:** No prompt may exceed 30,000 tokens when tokenized with cl100k_base.
Use `tiktoken` to check before writing to disk:

```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
assert len(enc.encode(prompt_text)) < 30_000
```

---

## Question format variants (required for diversity score)

Every underlying biological fact must be expressed in at least THREE of these formats:

| Format | Description | Example answer |
|--------|-------------|----------------|
| `binary_classification` | Yes/No question | `"yes"` |
| `ternary_classification` | Three-way choice | `"synergistic"` / `"antagonistic"` / `"additive"` |
| `regression` | Numeric prediction | `"-23.5"` (percent change as string) |
| `pairwise_comparison` | Which of A or B | `"A"` |
| `mcq` | Multiple choice, labeled A–D | `"B"` |
| `set_generation` | Comma-separated list | `"daf-16,hsf-1,skn-1"` |

**Negation variants are required.** For every positive question ("Is X overexpressed?"),
include a negation variant ("Which of these genes is NOT associated with lifespan extension?").
Models that have never seen negative results ace positive-only benchmarks. We expose this.

---

## Evaluation pipeline

### Model targets

| Model | Access method | Notes |
|-------|---------------|-------|
| L-LLM | HuggingFace endpoint (get token from organizers Saturday AM) | Primary target. Must collect full thinking traces. |
| GPT-4o | OpenAI API (`OPENAI_API_KEY` in `.env`) | Comparison baseline. |
| Majority class | Computed from train split label distribution | Required lower baseline. |
| Random uniform | Random label draw, 1000 seeds averaged | Required lower baseline. |

### Metrics (implement all — judges check)

```python
from sklearn.metrics import f1_score, balanced_accuracy_score
from scipy.stats import bootstrap
import numpy as np

def score_classification(y_true, y_pred, labels):
    return {
        "macro_f1": f1_score(y_true, y_pred, average="macro", labels=labels),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "ci_95": bootstrap(
            (np.array(y_true), np.array(y_pred)),
            lambda a, b: f1_score(a, b, average="macro"),
            n_resamples=1000,
            confidence_level=0.95
        ).confidence_interval
    }

def score_regression(y_true, y_pred):
    return {
        "mae": np.mean(np.abs(np.array(y_true) - np.array(y_pred))),
        "r2": 1 - np.sum((y_true - y_pred)**2) / np.sum((y_true - np.mean(y_true))**2)
    }
```

Always report the majority-class baseline F1 alongside model F1.
A model that scores 0.62 F1 on a task where majority-class gets 0.61 is not impressive.

---

## Trace scorer (extra credit — build this Sunday morning)

The trace scorer reads L-LLM's thinking trace and automatically verifies the biological claims
made inside it. It outputs a `trace_faithfulness` score between 0 and 1.

### Entity types to extract and verify

| Entity type | Example | Verification API |
|-------------|---------|-----------------|
| Human gene symbol | `FOXO3`, `MTOR`, `TP53` | NCBI Gene eutils (esearch + esummary) |
| C. elegans gene | `daf-2`, `age-1`, `clk-1` | WormBase REST API |
| Mouse gene | `Trp53`, `Igf1r` | MGI API |
| KEGG pathway | `hsa04151` (PI3K-Akt) | KEGG REST `/get/` |
| Gene–pathway claim | "FOXO3 is in the PI3K/AKT pathway" | NCBI Gene → KEGG link |
| Chromosome location | "gene X is on chromosome 6" | NCBI Gene esummary `.chromosome` field |
| Protein interaction | "protein A interacts with protein B" | STRING-DB `/network/` endpoint |

### Entity extraction

Do NOT use pure uppercase-word regex — it breaks on C. elegans genes (lowercase, hyphenated)
and on gene symbols at sentence starts.

Instead use a hybrid approach:

```python
import re

# Human/mouse genes: 2–10 uppercase letters, optionally followed by numbers
HUMAN_GENE_RE = re.compile(r'\b([A-Z][A-Z0-9]{1,9})\b')

# C. elegans genes: 3 lowercase letters, hyphen, number(s)
CELEGANS_GENE_RE = re.compile(r'\b([a-z]{2,4}-\d+[a-z]?)\b')

# Mouse genes: first letter uppercase, rest lowercase
MOUSE_GENE_RE = re.compile(r'\b([A-Z][a-z0-9]{1,9})\b')
```

Cross-reference every extracted token against a whitelist built from our task metadata
before hitting external APIs. Only call the API for tokens that appear in our organism's
known gene namespace.

### Consistency checker

After extracting the final answer label from the model response, compare it against the
direction stated in the trace:

```python
EXTEND_KEYWORDS = {"extend", "increase", "longer", "longevity", "pro-longevity"}
SHORTEN_KEYWORDS = {"shorten", "decrease", "shorter", "reduce lifespan", "detrimental"}

def check_consistency(trace: str, final_label: str) -> bool:
    trace_lower = trace.lower()
    trace_says_extend = any(kw in trace_lower for kw in EXTEND_KEYWORDS)
    trace_says_shorten = any(kw in trace_lower for kw in SHORTEN_KEYWORDS)
    if final_label == "increased" and trace_says_shorten and not trace_says_extend:
        return False  # inconsistent
    if final_label == "decreased" and trace_says_extend and not trace_says_shorten:
        return False  # inconsistent
    return True
```

### Trace faithfulness formula

```
trace_faithfulness = (
    0.4 * (verified_gene_claims / total_gene_claims)
  + 0.3 * (verified_pathway_claims / total_pathway_claims)
  + 0.3 * float(trace_consistent_with_final_answer)
)
```

Use `0.0` for any component where the denominator is zero (no claims of that type).

---

## API keys and environment

Copy `.env.example` to `.env` and fill in your keys. Never commit `.env`.

```bash
# .env.example
OPENAI_API_KEY=sk-...
HF_TOKEN=hf_...                          # L-LLM HuggingFace endpoint token (get from organizers)
HF_ENDPOINT_URL=https://...              # fill in once organizers share it
NCBI_API_KEY=...                         # optional but raises rate limit from 3 to 10 req/s
```

Load with:

```python
from dotenv import load_dotenv
import os
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
```

---

## Coding conventions

### Python style

- Python 3.11+
- Type hints on all function signatures
- Docstrings on every public function — one line summary, then Args/Returns if non-trivial
- 88-character line limit (Black default)
- Format with `black .` before committing
- Lint with `ruff check .`

### Error handling

All external API calls must have retry logic with exponential backoff. Use `tenacity`:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
def call_ncbi_api(gene_symbol: str) -> dict:
    ...
```

Never let an API failure crash the full eval run. Catch exceptions, log them, and write
`null` to the output field. The run must complete even if 5% of API calls fail.

### Reproducibility

Every function that involves randomness must accept a `seed: int = 42` parameter.
Log the seed used in every output file's metadata.

```python
import random
import numpy as np

def set_global_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
```

### Logging

Use Python's `logging` module, not `print`. Set level to `INFO` by default.

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger(__name__)
```

### Data validation

Use `pydantic` for all data models. Every record loaded from a raw database must be
validated before it enters the prompt pipeline:

```python
from pydantic import BaseModel, field_validator

class SynergyAgeRecord(BaseModel):
    gene_1: str
    gene_2: str
    organism: str
    single_1_pct: float
    single_2_pct: float
    combined_pct: float
    epistasis_type: str  # "synergistic" | "antagonistic" | "additive"

    @field_validator("epistasis_type")
    def valid_epistasis(cls, v):
        assert v in {"synergistic", "antagonistic", "additive"}, f"Unknown: {v}"
        return v
```

---

## Git workflow

We are a small team moving fast. Keep it simple:

- `main` — always runnable. Do not push broken code here.
- `feat/<your-name>/<short-description>` — feature branches. Merge via PR or direct push
  if you've verified it runs end-to-end.
- Commit messages: imperative, lowercase, under 72 chars.
  Examples: `add synergyage csv loader`, `fix ternary label mapping`, `add ncbi retry logic`
- If you break something, say so in Slack immediately. No judgment — we're under 48 hours.

---

## Running the pipeline end to end

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download raw data (do this first, Saturday morning)
python src/data_loaders/synergyage_loader.py --download
python src/data_loaders/mgi_loader.py --download

# 3. Generate prompts
python src/prompt_generators/task_a_generator.py --output data/processed/
python src/prompt_generators/task_b_generator.py --output data/processed/

# 4. Validate prompt files (checks token limits, JSONL format, N >= 50)
python src/eval/validate_prompts.py --dir data/processed/

# 5. Run evaluation (will take ~1–2 hours depending on API rate limits)
python src/eval/runner.py --tasks task_a task_b --models llm gpt4o majority random

# 6. Score results
python src/eval/scorer.py --results outputs/

# 7. Run trace scorer on L-LLM outputs
python src/trace_scorer/trace_scorer.py --input outputs/results_task_a.json

# 8. Generate gap analysis report
python src/analysis/gap_analysis.py --output outputs/gap_analysis_report.md
```

---

## Biological domain notes (read before writing any prompts)

### C. elegans gene naming conventions
- Genes: lowercase, 3 letters + hyphen + number. Examples: `daf-2`, `age-1`, `clk-1`, `eat-2`
- The model should know these — if it capitalizes them it is likely hallucinating

### Key longevity pathways (for consistency checking)
- **IIS pathway:** DAF-2 (insulin receptor) → AGE-1 (PI3K) → PDK-1 → AKT-1/2 → DAF-16 (FOXO)
- **TOR pathway:** LET-363 (mTOR) → S6K (rsks-1) — inhibition extends lifespan
- **Mitochondrial:** clk-1, isp-1 — partial loss of function extends lifespan
- **Germline:** removal of germline stem cells (glp-1 mutants) extends lifespan via DAF-16 and DAF-12

### Mouse lifespan phenotype ontology terms we use
- `MP:0010765` — increased lifespan (→ label: `"increased"`)
- `MP:0010767` — decreased lifespan (→ label: `"decreased"`)
- `MP:0002058` — normal lifespan (→ label: `"no_change"`)

### Common class imbalance issues
SynergyAge skews toward synergistic interactions (they are more interesting to publish).
MGI skews toward decreased lifespan (gain-of-function mutations that kill mice are common).
Always check label distributions after loading and report them in comments.
Use balanced accuracy and macro F1 (not plain accuracy) in all reported metrics.

---

## What done looks like (Sunday PM checklist)

- [ ] `data/processed/task_a_train.jsonl` — ≥100 prompts, all formats present
- [ ] `data/processed/task_a_test.jsonl` — ≥50 prompts, organism-split from train
- [ ] `data/processed/task_b_train.jsonl` — ≥100 prompts, all formats present
- [ ] `data/processed/task_b_test.jsonl` — ≥50 prompts, chromosome-split from train
- [ ] `outputs/results_task_a.json` — L-LLM + GPT-4o + baselines, all scored
- [ ] `outputs/results_task_b.json` — same
- [ ] `outputs/gap_analysis_report.md` — key finding: where L-LLM beats GPT-4o and where it fails
- [ ] `outputs/trace_faithfulness_scores.json` — correlation between trace score and accuracy
- [ ] All JSONL files pass token limit validation (< 30K tokens per prompt)
- [ ] README.md written — explains what we built and how to reproduce it

---

## Questions / decisions log

Use this section to record non-obvious decisions made during the hackathon so teammates
don't re-litigate them.

| Decision | Rationale | Who decided | When |
|----------|-----------|-------------|------|
| Train/test split for Task A by organism, not random | Random split leaks data — same organism's genes appear in both splits | — | — |
| Report macro F1 as primary metric (not accuracy) | Class imbalance in both tasks makes accuracy misleading | — | — |
| Use cl100k_base tokenizer for length checks | Required by track spec | — | — |
