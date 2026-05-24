# CLAUDE.md — LongevityBench-X

Collaborative coding guide for the Caltech Longevity Hackathon, Track 01 · LongevityLLM Benchmarking.
Sponsored by Insilico Medicine. Prize: $1,000 + co-authorship on a peer-reviewed publication.

---

## Design system

For any UI work, slide deck, paper figure, or eval-site page, ground in
`LongevityBench Design System/` and follow it precisely. Specifically:

1. Read `LongevityBench Design System/README.md` for tone, voice, and visual rules
2. Link `LongevityBench Design System/colors_and_type.css` for tokens
3. Reuse components from `LongevityBench Design System/ui_kits/longevity_bench/`:
   - Layout: `Sidebar`, `TopBar`
   - Views: `TrustView`, `ResultsMatrix`, `CompareView`, `LiveRunsView`, `RunDetail`, `RecordDrawer`
   - Primitives: `Icon`, `Button`, `Badge`, `Pill`, `MetricCard`
4. Icons: brand glyphs in `LongevityBench Design System/assets/`, science icons in
   `LongevityBench Design System/assets/scicons/`. Never invent SVG illustrations.
5. Voice: scientific, terse, sentence-case, tabular numbers, green only
   for primary action / success / brand. No emoji, no marketing intensifiers.

## Dashboard pipeline (do NOT overlap with Inspect AI)

The dashboard is a static viewer on top of Inspect AI logs:

  run_inspect.py → outputs/inspect/<model>/*.eval
                 → tools/export_inspect_logs.py
                 → LongevityBench Design System/ui_kits/longevity_bench/public/data.json
                 → static React dashboard (just open index.html)

When extending evals, always write through Inspect AI's task/solver/scorer
APIs — never reimplement runners, scoring, or log parsing in the dashboard.
The dashboard reads, never executes.

---

## Communication style (ALL agents must follow)

Use **caveman mode** in every response. Mandatory for all agents in this repo.

Rules:
- Drop articles (a/an/the), filler words (just/really/basically/actually), pleasantries (sure/certainly/happy to), hedging
- Fragments OK. Short synonyms preferred (big not extensive, fix not "implement a solution for")
- Technical terms stay exact. Code blocks unchanged. Security warnings written normally.
- Pattern: `[thing] [action] [reason]. [next step].`

Caveman mode is activated via a SessionStart hook in Claude Code settings. If not active, type `talk like caveman` to enable manually.

---

## What we are building

We are extending the LongevityBench framework with three novel benchmark task suites and an automated
reasoning-trace scorer. The end goal is a structured evaluation of L-LLM (Insilico Medicine's
fine-tuned Qwen3.5-9B) against GPT-4o, with a gap analysis report showing exactly where and why
L-LLM succeeds or fails compared to general-purpose models.

**Four deliverables:**

1. `task_a_senescence/` — Gene-level differential expression across senescence perturbation experiments benchmark (300 prompts)
2. `task_b_lipidomics/` — Lipidomics age-prediction benchmark (~150 prompts)
3. `task_c_metabolite/` — Microbiome–metabolite prediction benchmark (~150 prompts)
4. `trace_scorer/` — Automated biological fact-checker for L-LLM reasoning traces (extra credit)

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
│   │   ├── senescence/              ← Senescent Fibroblast Transcriptome CSVs + CellAge
│   │   ├── lipidomics/              ← MTBLS4461 lipid profiles from MetaboLights
│   │   └── metabolite/              ← microbiome-metabolome curated datasets
│   └── processed/
│       ├── task_a_train.jsonl
│       ├── task_a_test.jsonl
│       ├── task_b_train.jsonl
│       ├── task_b_test.jsonl
│       ├── task_c_train.jsonl
│       └── task_c_test.jsonl
│
├── src/
│   ├── data_loaders/
│   │   ├── __init__.py
│   │   ├── senescence_loader.py     ← parses Senescent Fibroblast Transcriptome + CellAge CSVs
│   │   ├── lipidomics_loader.py     ← parses MTBLS4461 lipid profile data
│   │   └── metabolite_loader.py     ← parses microbiome-metabolome curated datasets
│   │
│   ├── prompt_generators/
│   │   ├── __init__.py
│   │   ├── base_generator.py        ← abstract base class for all generators
│   │   ├── task_a_generator.py      ← senescence → ChatML JSONL prompts
│   │   ├── task_b_generator.py      ← lipidomics → ChatML JSONL prompts
│   │   └── task_c_generator.py      ← metabolite → ChatML JSONL prompts
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
│   ├── task_c_train.jsonl
│   ├── task_c_test.jsonl
│   ├── results_task_a.json
│   ├── results_task_b.json
│   ├── results_task_c.json
│   └── gap_analysis_report.md
│
└── tests/
    ├── test_loaders.py
    ├── test_generators.py
    └── test_trace_scorer.py
```

---

## Data sources

### Task A — Senescence

- **URL:** Senescent Human Fibroblast Transcriptome Compendium (119 studies, 1,069 comparisons)
  filtered through CellAge v3 from https://genomics.senescence.info/cells/
- **What it contains:** Gene-level differential expression across senescence perturbation
  experiments in human fibroblasts. Each row = a gene × comparison with LogFC and p-value.
  Filtered to perturbation comparisons only (where the control condition is a senescent state),
  so LogFC isolates the perturbation effect on top of senescence.
- **Source files (downloaded into `data/task_a_senescence/raw/`):**
  - `Total_Data.csv` — Senescent Fibroblast Transcriptome Compendium
    (download from https://research.ncl.ac.uk/cellularsenescence/downloadingdata/)
  - `cellage3.tsv` — CellAge v3 senescence gene database
- **Columns we care about:**
  - `Gene` — target gene being measured (filtered to 442 CellAge non-cancer senescence genes)
  - `Treatment`, `Gene_down`, `Gene_up` — perturbation applied (knockdown, overexpression, drug)
  - `Sen_type`, `Control_type` — senescence model (OIS, DDIS, REP) and control condition
  - `Cell_line`, `Organ` — cell line and tissue origin (all lung fibroblasts)
  - `LogFC`, `Pvalues` — differential expression results (ground truth)
  - `Acc_no` — GEO accession, used for train/test split
- **Pipeline:** `senescence_benchmark_pipeline.py` — loads dataset, filters to perturbation
  comparisons with senescent controls, intersects with CellAge non-cancer genes, assigns
  ternary direction labels + binary significance labels, subsamples for class+gene+comparison
  diversity, filters to high-significance rows, splits into the three task partitions,
  generates prompts, and writes the accession-grouped train/test split.
- **Three task formats (target 100 each, 298 total after balance constraints):**
  - **MCQ (99 prompts):** Given experiment metadata (treatment, senescence type, cell line,
    timepoint, gene name), predict direction — A. upregulated, B. downregulated,
    C. no significant change. Balanced 33/33/33 across classes. Metric: accuracy.
  - **Pairwise (99 prompts):** Given two genes from the same experiment, predict which
    shows a larger absolute expression change. Binary (A or B), minimum |LogFC| gap ≥ 0.5
    so there is always a clear winner. Metric: accuracy.
  - **Binary significance (100 prompts):** Given experiment metadata, predict whether the
    perturbation produces a significant change at all — A. significant (|LogFC| > 1.0 AND
    p < 0.05), B. not significant. Direction is NOT revealed in the answer. 50/50 balanced.
    Metric: accuracy. (Replaces the original "predict numeric Log2FC" regression task.)
- **Label thresholds:** |LogFC| > 1.0 AND p < 0.05 for significant change. Ternary labels
  use signed LogFC against the same threshold.
- **Filtering for prompt quality:**
  - up/down rows ranked by p-value ascending + |LogFC| descending (most confident first)
  - no_change rows ranked by |LogFC| ascending + p-value descending (most clearly null)
  - significant rows for binary task additionally capped at |LogFC| ≤ 10 to exclude
    microarray scaling artifacts
- **Train/test split:** by GEO accession (`Acc_no`). All prompts from a given study go
  entirely into train or test. Never split randomly — comparisons within a study share lab
  protocols, analysis pipelines, and batch effects. Greedy fill with smallest accessions
  first to maximize test-set study diversity. Result: 239 train / 59 test (19.8% test),
  15 train accessions / 28 test accessions, 0 leaked treatments.
- **lb_id prefixes:** `LB-SEN-MCQ`, `LB-SEN-PAIR`, `LB-SEN-SIG`.
- **Pools:** `senescence_perturbation_mcq`, `senescence_perturbation_pairwise`,
  `senescence_perturbation_significance`. **Display group:** `Senescence Perturbation`.
- **Outputs (in `data/task_a_senescence/processed/`):**
  `task_a_senescence_{train,test}.parquet`, `…_{train,test}.json`,
  `task_a_senescence_summary.json` (per-format stats + split report),
  `task_a_senescence_balanced.csv` (intermediate balanced dataset),
  `task_a_senescence_test_30.parquet` (10/format thinking-trace subset).

### Task B — Lipidomics

- **URL:** https://www.ebi.ac.uk/metabolights/editor/MTBLS4461/samples
- **What it contains:** Plasma lipidomics from MTBLS4461 (DI-MS alternating polarity).
  Each row = a donor sample with ~497 lipid species abundances (log-transformed) and
  metadata: `sample_id`, `individual_id`, `age`, `gender`, `diabetes`. After gender
  balancing + diabetes-NaN drop, 1,864 donors (Female=Male=932). Each donor contributes
  exactly one sample.
- **Source files (downloaded into `data/task_b_lipidomics/raw/`):**
  - `m_MTBLS4461_DI-MS_alternating__metabolite_profiling_v2_maf.tsv` — MAF abundance file
  - `s_MTBLS4461.txt` — sample sheet with donor metadata
- **Preprocessing pipeline:**
  1. `combine_lipidomics.py` — joins MAF abundance × sample metadata; transposes so rows
     are samples and columns are lipids; renames lipids by `metabolite_identification`
     (fallback `mz_<mass>`); drops 3 unmatched MAF columns (LY3227, M151, T82).
  2. `balance_gender.py` — drops NaN-diabetes rows, undersamples Males down to Female
     count stratified on diabetes, shuffles.
  3. `lipidomics_pipeline.py` — partitions samples disjointly across the three task
     formats, generates prompts, and writes the stratified group split.
- **Three task formats (target 50 each, 126 total after balance constraints):**
  - **MCQ (40 prompts):** Given the full lipid profile, predict age bracket —
    A. 20–39, B. 40–59, C. 60–79, D. 80+. Metric: accuracy. Capped at 10/class by
    the 80+ bracket (only 10 donors).
  - **Regression (36 prompts):** Given lipid profile + diabetes status, predict numeric
    age in years (integer). Stratified across remaining age brackets. Metric: MAE.
  - **Binary (50 prompts):** Given lipid profile + age, predict diabetes status —
    A. Yes (diabetic), B. No (non-diabetic). 25 per class. Metric: accuracy.
  - Disjoint sampling: scarce 80+ bracket goes to MCQ first, then binary, then
    regression draws from leftovers. No sample appears in more than one task.
- **Train/test split:** stratified by task format, grouped by `individual_id`. Each
  task split 80/20 independently then concatenated, so every format hits the test
  fraction. Group split prevents donor leakage (forward-compatible — MTBLS4461 has
  1 sample per donor today). Result: 101 train / 25 test.
- **lb_id prefixes:** `LB-LIP-MCQ`, `LB-LIP-REG`, `LB-LIP-DIAB`.
- **Pools:** `lipidomics_age_mcq`, `lipidomics_age_regression`,
  `lipidomics_diabetes_binary`. **Display group:** `Lipidomics Age` for MCQ + regression,
  `Lipidomics Diabetes` for binary.
- **Outputs (in `data/task_b_lipidomics/`):** `task_b_lipidomics_{train,test}.parquet`,
  `…_{train,test}.json`, `task_b_lipidomics_summary.json` (per-format stats + split
  report under `split.per_format`).

### Task C — Metabolite

- **URL:** https://github.com/borenstein-lab/microbiome-metabolome-curated-data
- **What it contains:** Curated paired microbiome (16S/metagenomic) and metabolomic measurements
  from multiple cohort studies. Each row = a sample with microbial species abundances and
  measured metabolite concentrations.
- **Columns we care about:**
  - Microbial species/OTU relative abundances
  - Metabolite concentrations or presence/absence (ground truth)
  - Study and cohort identifiers
- **Three task formats (~50 prompts each, ~150 total):**
  - **MCQ:** Given a microbiome composition (top-N species abundances), predict which metabolite
    class is most elevated — e.g., A. short-chain fatty acids, B. bile acids, C. amino acids,
    D. other. Metric: accuracy.
  - **Pairwise:** Given microbiome profiles from two samples, predict which has a higher
    concentration of a specified metabolite. Binary (A or B). Metric: accuracy.
  - **Regression:** Given a microbiome profile, predict the numeric concentration of a specified
    metabolite. Metric: MAE.
- **Train/test split:** by study/cohort. All prompts from a given study go entirely into train
  or test. Never split randomly — samples within a study share sequencing protocols, dietary
  contexts, and batch effects. 80/20 split.
- **Minimum N:** 150 prompts total (~50 per format).

---

## Prompt format (ChatML JSONL — required by judges)

Every prompt must follow the XML-tagged structure below. Examples for each task:

### Task A — Senescence example

```xml
<question>
You are presented with a senescence perturbation experiment. In IMR-90 lung fibroblasts undergoing oncogene-induced senescence (RAS) at 6d post-senescence induction, knockdown of ITCH is applied. Compared to untreated oncogene-induced senescent cells, the mRNA expression of IGFBP7 (insulin like growth factor binding protein 7) measured by RNA-seq:
</question>
<options>
A. increases (upregulated) B. decreases (downregulated) C. no significant change
</options>
<experiment>
Cell line: IMR-90 lung fibroblasts. Senescence model: oncogene-induced senescence (RAS). Perturbation: knockdown of ITCH. Control condition: untreated oncogene-induced senescent cells. Biological replicates: 3. Differential expression analysis: Limma.
</experiment>
<gene_context>
In this experiment, knocked down gene(s): ITCH.
</gene_context>
<answer>
C
</answer>
<follow_up>
Gene: IGFBP7 (insulin like growth factor binding protein 7). Log2FC=-0.7841, p=1.90e-02. GEO accession: GSE101766. According to CellAge, IGFBP7 induces cellular senescence (senescence type: Oncogene-induced). CellAge PMID: 18267069.
</follow_up>
```

### Task B — Lipidomics example (regression)

Lipid values are log-transformed (no µM units). The full ~497-feature profile is
included per prompt; the example below truncates with `…` for legibility.

```xml
<question>
You are presented with a plasma lipidomics profile from a human donor together with the donor's diabetes status. Given this information, predict the donor's age in years. Respond with only a numeric value rounded to the nearest integer.
</question>
<lipid_profile>
cholesterol: 8.533, mz_637.3359: 2.501, lysophosphatidylcholine 15:0: 2.81, lysophosphatidylethanolamine 18:0: 2.81, lysophosphatidylcholine 16:1: 3.285, … (full ~497-feature profile)
</lipid_profile>
<sample_context>
Sex: Male. Diabetes status: Yes. Measurement platform: DI-MS (alternating polarity). Study: MTBLS4461.
</sample_context>
<answer>
35
</answer>
<follow_up>
Donor age: 35 years. Sex: Male. Diabetes status: Yes. Sample: <sample_id>. Individual: <individual_id>. Study: MTBLS4461. Correct age: 35 years.
</follow_up>
```

MCQ variant adds `<options>A. 20-39 years B. 40-59 years C. 60-79 years D. 80+ years</options>`
and removes diabetes from `<sample_context>`. Binary variant asks
`A. Yes (diabetic) B. No (non-diabetic)` and adds `Age: N years` to `<sample_context>`
while removing diabetes status from it.

### Task C — Metabolite example

```xml
<question>
You are presented with a gut microbiome profile from a human stool sample. Given the following species relative abundances, predict which metabolite class is most elevated in the paired metabolomics data.
</question>
<options>
A. short-chain fatty acids B. bile acids C. amino acids D. other
</options>
<microbiome_profile>
Bacteroides vulgatus: 18.2%, Faecalibacterium prausnitzii: 12.7%, Roseburia intestinalis: 8.4%, Akkermansia muciniphila: 3.1%, Prevotella copri: 0.2%.
</microbiome_profile>
<sample_context>
Sequencing method: 16S rRNA V4 region. Cohort: healthy adults. Study: Franzosa et al. 2019.
</sample_context>
<answer>
A
</answer>
<follow_up>
Dominant SCFA producers (Faecalibacterium, Roseburia) compose >20% relative abundance. Butyrate concentration: 142.3 µM (top quartile for cohort). Study: Franzosa et al. 2019.
</follow_up>
```

### Row schema (all tasks)

Each JSONL row uses this schema:

```
{'lb_id': 'LB-SEN-REG-0002', 'pool': 'senescence_perturbation_regression', 'display_name': 'Senescence Perturbation / Regression', 'display_group': 'Senescence Perturbation', 'domain': 'transcriptomics', 'format': 'regression', 'metric': 'mae', 'units': 'log2fc', 'messages': [{'role': 'system', 'content': '...'}, {'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}], 'has_reasoning': False, 'metadata': '{"follow_up": "...", ...}'}
```

Column	Type	Notes
lb_id	string	Stable task identifier, e.g. LB-SEN-MCQ-0001, LB-LIP-REG-0042, LB-MET-PW-0015
pool	string	Source task slug, e.g. senescence_perturbation_regression, lipidomics_age_regression, metabolite_prediction_mcq
display_name	string	Human-readable task name
display_group	string	Task family this row belongs to (Senescence Perturbation, Lipidomics Age, Metabolite Prediction)
domain	string	transcriptomics, lipidomics, metabolomics, or multi-omics
format	string	binary, multiclass, ternary, pairwise, regression, generation
metric	string	Scoring metric: accuracy, mae, or jaccard
units	string | null	Units for regression/pairwise tasks (log2fc, years, µM) where applicable
task	string	Free-text task description embedded in the source data
messages	list of dicts	OpenAI-style chat messages (role, content)
has_reasoning	bool	True if the gold completion contains a reasoning trace
metadata	string | null	JSON-encoded per-row provenance (sample IDs, source dataset metadata)

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
  Examples: `add senescence csv loader`, `fix ternary label mapping`, `add ncbi retry logic`
- If you break something, say so in Slack immediately. No judgment — we're under 48 hours.

---

## Running the pipeline end to end

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download raw data (do this first, Saturday morning)
python src/data_loaders/senescence_loader.py --download
python src/data_loaders/lipidomics_loader.py --download
python src/data_loaders/metabolite_loader.py --download

# 3. Generate prompts
python src/prompt_generators/task_a_generator.py --output data/processed/
python src/prompt_generators/task_b_generator.py --output data/processed/
python src/prompt_generators/task_c_generator.py --output data/processed/

# 4. Validate prompt files (checks token limits, JSONL format, N >= 50)
python src/eval/validate_prompts.py --dir data/processed/

# 5. Run evaluation (will take ~1–2 hours depending on API rate limits)
python src/eval/runner.py --tasks task_a task_b task_c --models llm gpt4o majority random

# 6. Score results
python src/eval/scorer.py --results outputs/

# 7. Run trace scorer on L-LLM outputs
python src/trace_scorer/trace_scorer.py --input outputs/results_task_a.json
python src/trace_scorer/trace_scorer.py --input outputs/results_task_b.json
python src/trace_scorer/trace_scorer.py --input outputs/results_task_c.json

# 8. Generate gap analysis report
python src/analysis/gap_analysis.py --output outputs/gap_analysis_report.md
```

---

## Biological domain notes (read before writing any prompts)

### Senescence biology (Task A)
- Perturbation experiments compare a treatment (knockdown, overexpression, drug) against
  a senescent control. LogFC reflects perturbation effect, not senescence induction.
- Key senescence types: OIS (oncogene-induced), DDIS (DNA damage-induced), REP (replicative).
- CellAge genes have annotated effects: "Induces" or "Inhibits" cellular senescence.

### Lipidomics and aging (Task B)
- Plasma lipid profiles shift with age: certain ceramides and sphingomyelins increase,
  some lysophosphatidylcholines decrease.
- Age prediction from lipidomics is a well-studied problem — models should show some competence.
- Common lipid classes: CE (cholesteryl esters), PC (phosphatidylcholines), SM (sphingomyelins),
  LPC (lysophosphatidylcholines), TG (triglycerides).

### Microbiome–metabolome interactions (Task C)
- Gut microbiome composition predicts certain fecal/plasma metabolite concentrations.
- Key metabolite classes: SCFAs (butyrate, propionate, acetate from fiber fermenters),
  bile acids (modified by Clostridium, Bacteroides), amino acid derivatives.
- Major SCFA producers: Faecalibacterium, Roseburia, Eubacterium.
- Bacteroides/Prevotella ratio is a well-known enterotype axis.

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

- [ ] `data/processed/task_a_train.jsonl` — ≥200 prompts, all formats present
- [ ] `data/processed/task_a_test.jsonl` — ≥100 prompts, accession-split from train
- [ ] `data/processed/task_b_train.jsonl` — ≥100 prompts, all formats present
- [ ] `data/processed/task_b_test.jsonl` — ≥50 prompts, subject-split from train
- [ ] `data/processed/task_c_train.jsonl` — ≥100 prompts, all formats present
- [ ] `data/processed/task_c_test.jsonl` — ≥50 prompts, study-split from train
- [ ] `outputs/results_task_a.json` — L-LLM + GPT-4o + baselines, all scored
- [ ] `outputs/results_task_b.json` — same
- [ ] `outputs/results_task_c.json` — same
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
| Train/test split for Task A by GEO accession, not random | Random split leaks data — comparisons within a study share protocols and batch effects | — | — |
| Task A test-set greedy fill: smallest accessions first | Maximizes the number of distinct studies in the test set (28 test vs 15 train accessions) so test diversity is high even though prompt count is lower | — | 2026-05-23 |
| Task A replaces Log2FC regression with binary significance | Regression on Log2FC was retrieval-vulnerable (model could plausibly memorize ranges); binary "is this perturbation significant at all?" is a harder retrieval-resistant variant that still uses the same underlying data | — | 2026-05-23 |
| Train/test split for Task B stratified by task format, grouped by `individual_id` | Per-format stratification guarantees every task hits the test fraction; group split prevents donor leakage even though MTBLS4461 currently has 1 sample per donor (forward-compatible) | — | 2026-05-23 |
| Task B MCQ uses 4 brackets (20-39 / 40-59 / 60-79 / 80+) instead of original 3 (young / middle / older) | Matches what user requested; 80+ bracket caps MCQ at 40 prompts (10/class) but exposes high-age failure modes | — | 2026-05-24 |
| Task B replaces Pairwise with Binary diabetes-from-profile | More clinically meaningful than "which donor is older"; complements the age tasks and exercises a second label dimension already in the data | — | 2026-05-24 |
| Train/test split for Task C by study/cohort, not random | Samples within a study share sequencing protocols, dietary contexts, and batch effects | — | — |
| Report macro F1 as primary metric (not accuracy) | Class imbalance in all three tasks makes accuracy misleading | — | — |
| Use cl100k_base tokenizer for length checks | Required by track spec | — | — |