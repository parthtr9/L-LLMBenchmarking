"""
Senescence Perturbation Benchmark Pipeline
==========================================
Loads a senescent fibroblast transcriptome dataset, filters to perturbation
comparisons with senescent controls, intersects with CellAge non-cancer genes,
assigns ternary expression labels, subsamples for balance, and generates
evaluation prompts from metadata only.

The balanced data is split three ways into different task formats:
  - MCQ (1/3):      Ternary classification (up / down / no change)
  - Pairwise (1/3): Which of two genes shows a larger absolute expression change?
  - Regression (1/3): Predict the numeric Log2FC value

Inputs:
    - dataset.csv: Gene-level differential expression across senescence comparisons
    - cellage3.tsv: CellAge database of senescence-associated genes

Outputs (all saved as both parquet and JSON):
    - benchmark_train.{parquet,json}:   Training set (80%, all formats mixed)
    - benchmark_test.{parquet,json}:    Test set (20%, all formats mixed)
    - benchmark_summary.json:           Statistics across all formats + split report
    
    Split by GEO accession to prevent data leakage. Treatment leakage is
    reported but not used as a splitting covariate (accession subsumes it
    in most cases).
"""

import pandas as pd
import numpy as np
import json
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. LOAD & FILTER DATASET
# ---------------------------------------------------------------------------

def load_dataset(path: str) -> pd.DataFrame:
    """Load the senescence transcriptome dataset."""
    df = pd.read_csv(path, low_memory=False)
    print(f"Loaded dataset: {len(df):,} rows, {df['Comparison'].nunique()} comparisons")
    return df


def filter_perturbations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only perturbation comparisons:
    - Treatment is not 'none' (an actual intervention was applied)
    - Control_type is a senescent condition (OIS, DDIS, REP)
      so LogFC reflects the perturbation effect on top of senescence
    """
    senescent_controls = ['OIS', 'DDIS', 'REP']

    mask = (
        (df['Treatment'] != 'none') &
        (df['Control_type'].isin(senescent_controls))
    )
    filtered = df[mask].copy()

    print(f"After perturbation filter: {len(filtered):,} rows, "
          f"{filtered['Comparison'].nunique()} comparisons")
    print(f"  Control types: {dict(filtered.groupby('Control_type')['Comparison'].nunique())}")
    print(f"  Unique treatments: {filtered['Treatment'].nunique()}")
    return filtered


# ---------------------------------------------------------------------------
# 2. LOAD CELLAGE & INTERSECT
# ---------------------------------------------------------------------------

def load_cellage(path: str) -> pd.DataFrame:
    """Load CellAge database, keep non-cancer genes only."""
    cellage = pd.read_csv(path, sep='\t')
    print(f"Loaded CellAge: {len(cellage)} entries")

    # Filter to non-cancer cell lines
    non_cancer = cellage[cellage['Cancer Cell'] == 'No'].copy()
    print(f"After removing cancer lines: {len(non_cancer)} entries, "
          f"{non_cancer['Gene symbol'].nunique()} unique genes")
    return non_cancer


def intersect_with_cellage(df: pd.DataFrame, cellage: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows where Gene matches a CellAge non-cancer gene.
    Merge CellAge annotations (gene name, senescence effect, senescence type, PMID)."""
    cellage_genes = set(cellage['Gene symbol'].unique())
    intersected = df[df['Gene'].isin(cellage_genes)].copy()

    # Build a lookup from CellAge: one row per gene (take first entry if duplicates)
    cellage_lookup = (cellage
        .drop_duplicates(subset='Gene symbol', keep='first')
        [['Gene symbol', 'Gene name', 'Senescence Effect', 'Type of senescence', 'Reference']]
        .rename(columns={
            'Gene symbol': 'Gene',
            'Gene name': 'cellage_gene_name',
            'Senescence Effect': 'cellage_senescence_effect',
            'Type of senescence': 'cellage_senescence_type',
            'Reference': 'cellage_pmid',
        })
    )
    intersected = intersected.merge(cellage_lookup, on='Gene', how='left')

    print(f"After CellAge intersection: {len(intersected):,} rows, "
          f"{intersected['Gene'].nunique()} genes, "
          f"{intersected['Comparison'].nunique()} comparisons")
    return intersected


# ---------------------------------------------------------------------------
# 3. ASSIGN TERNARY LABELS
# ---------------------------------------------------------------------------

def assign_labels(
    df: pd.DataFrame,
    logfc_threshold: float = 1.0,
    pvalue_threshold: float = 0.05,
) -> pd.DataFrame:
    """
    Assign ternary direction labels:
      - 'upregulated':   LogFC >  threshold AND p < pvalue_threshold
      - 'downregulated': LogFC < -threshold AND p < pvalue_threshold
      - 'no_change':     everything else
    """
    conditions = [
        (df['LogFC'] > logfc_threshold) & (df['Pvalues'] < pvalue_threshold),
        (df['LogFC'] < -logfc_threshold) & (df['Pvalues'] < pvalue_threshold),
    ]
    choices = ['upregulated', 'downregulated']
    df['direction'] = np.select(conditions, choices, default='no_change')

    counts = df['direction'].value_counts()
    print(f"Label distribution:")
    for label, count in counts.items():
        print(f"  {label}: {count:,}")
    return df


# ---------------------------------------------------------------------------
# 4. SUBSAMPLE FOR BALANCE
# ---------------------------------------------------------------------------

def subsample_balanced(
    df: pd.DataFrame,
    max_per_gene: int = 3,
    max_per_comparison: int = 5,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Subsample to equal counts per ternary label, with diversity caps
    on how many prompts any single gene or comparison can contribute.
    """
    rng = np.random.RandomState(random_state)
    sampled_parts = []

    for direction in ['upregulated', 'downregulated', 'no_change']:
        pool = df[df['direction'] == direction].copy()

        # Cap per gene: keep at most max_per_gene rows per gene
        keep_idx = []
        for gene, group in pool.groupby('Gene'):
            if len(group) > max_per_gene:
                keep_idx.extend(group.sample(max_per_gene, random_state=rng).index.tolist())
            else:
                keep_idx.extend(group.index.tolist())
        pool = pool.loc[keep_idx].copy()

        # Cap per comparison: keep at most max_per_comparison rows per comparison
        keep_idx = []
        for comp, group in pool.groupby('Comparison'):
            if len(group) > max_per_comparison:
                keep_idx.extend(group.sample(max_per_comparison, random_state=rng).index.tolist())
            else:
                keep_idx.extend(group.index.tolist())
        pool = pool.loc[keep_idx].copy()

        sampled_parts.append(pool)

    # Find the smallest class size and match all classes to it
    min_class = min(len(part) for part in sampled_parts)
    balanced_parts = []
    for part in sampled_parts:
        if len(part) > min_class:
            balanced_parts.append(part.sample(min_class, random_state=rng))
        else:
            balanced_parts.append(part)

    balanced = pd.concat(balanced_parts, ignore_index=True)
    balanced = balanced.sample(frac=1, random_state=rng).reset_index(drop=True)

    print(f"\nBalanced benchmark set: {len(balanced)} prompts")
    print(f"  Per class: {min_class}")
    print(f"  Unique genes: {balanced['Gene'].nunique()}")
    print(f"  Unique comparisons: {balanced['Comparison'].nunique()}")
    print(f"  Unique accessions: {balanced['Acc_no'].nunique()}")
    print(f"  Unique treatments: {balanced['Treatment'].nunique()}")
    print(f"  Unique cell lines: {balanced['Cell_line'].nunique()}")
    return balanced


# ---------------------------------------------------------------------------
# 4b. FILTER TO HIGH-SIGNIFICANCE ROWS
# ---------------------------------------------------------------------------

def filter_high_significance(
    df: pd.DataFrame,
    target_per_class: int = 100,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Keep only the most statistically significant rows from each direction class.

    For 'upregulated' and 'downregulated': rank by p-value ascending (most
    significant first), then by |LogFC| descending as tiebreaker.
    For 'no_change': rank by |LogFC| ascending (closest to zero = most clearly
    unchanged), then by p-value descending (least significant = most confidently
    unchanged).

    We keep target_per_class * 3 rows per class to give the three-way split
    enough rows (each task format gets ~target_per_class rows).
    """
    rng = np.random.RandomState(random_state)
    pool_size = target_per_class * 3  # enough for three-way split

    parts = []
    for direction in ['upregulated', 'downregulated', 'no_change']:
        pool = df[df['direction'] == direction].copy()
        pool['abs_logfc'] = pool['LogFC'].abs()

        if direction in ('upregulated', 'downregulated'):
            # Most significant: lowest p-value, highest |LogFC|
            pool = pool.sort_values(
                ['Pvalues', 'abs_logfc'],
                ascending=[True, False],
            )
        else:
            # Most clearly unchanged: smallest |LogFC|, highest p-value
            pool = pool.sort_values(
                ['abs_logfc', 'Pvalues'],
                ascending=[True, False],
            )

        n_keep = min(len(pool), pool_size)
        pool = pool.head(n_keep).drop(columns='abs_logfc')
        parts.append(pool)

    filtered = pd.concat(parts, ignore_index=True)
    filtered = filtered.sample(frac=1, random_state=rng).reset_index(drop=True)

    min_class = min(len(p) for p in parts)
    print(f"\nHigh-significance filter (target {target_per_class} per class × 3 formats):")
    print(f"  Kept {len(filtered)} rows (min class: {min_class})")
    for direction in ['upregulated', 'downregulated', 'no_change']:
        subset = filtered[filtered['direction'] == direction]
        print(f"  {direction}: {len(subset)} rows, "
              f"median p={subset['Pvalues'].median():.2e}, "
              f"median |LogFC|={subset['LogFC'].abs().median():.3f}")

    return filtered


# ---------------------------------------------------------------------------
# 4c. EDA ON BALANCED SET
# ---------------------------------------------------------------------------

def run_eda(df: pd.DataFrame) -> None:
    """Print detailed summary statistics and stratifications for the balanced set."""

    sep = "-" * 50
    print(f"\n{'=' * 60}")
    print("EXPLORATORY DATA ANALYSIS — BALANCED BENCHMARK SET")
    print(f"{'=' * 60}")

    # --- Overall shape ---
    print(f"\n{sep}")
    print("OVERALL")
    print(sep)
    print(f"  Total rows (prompts):     {len(df):,}")
    print(f"  Unique genes:             {df['Gene'].nunique()}")
    print(f"  Unique comparisons:       {df['Comparison'].nunique()}")
    print(f"  Unique accessions (GSE):  {df['Acc_no'].nunique()}")
    print(f"  Unique treatments:        {df['Treatment'].nunique()}")
    print(f"  Unique cell lines:        {df['Cell_line'].nunique()}")
    print(f"  Unique senescence types:  {df['Sen_type'].nunique()}")

    # --- Label distribution ---
    print(f"\n{sep}")
    print("LABEL DISTRIBUTION")
    print(sep)
    label_counts = df['direction'].value_counts()
    for label, count in label_counts.items():
        pct = 100 * count / len(df)
        print(f"  {label:20s}  {count:5d}  ({pct:.1f}%)")

    # --- LogFC statistics per label ---
    print(f"\n{sep}")
    print("LogFC STATISTICS BY LABEL")
    print(sep)
    for label in ['upregulated', 'downregulated', 'no_change']:
        subset = df[df['direction'] == label]
        if len(subset) == 0:
            continue
        print(f"  {label}:")
        print(f"    mean |LogFC| = {subset['LogFC'].abs().mean():.3f}")
        print(f"    median |LogFC| = {subset['LogFC'].abs().median():.3f}")
        print(f"    range = [{subset['LogFC'].min():.3f}, {subset['LogFC'].max():.3f}]")
        print(f"    mean p-value = {subset['Pvalues'].mean():.4e}")

    # --- Senescence type breakdown ---
    print(f"\n{sep}")
    print("STRATIFICATION: SENESCENCE TYPE")
    print(sep)
    ct = pd.crosstab(df['Sen_type'], df['direction'], margins=True)
    print(ct.to_string())

    # --- Control type breakdown ---
    print(f"\n{sep}")
    print("STRATIFICATION: CONTROL TYPE")
    print(sep)
    ct = pd.crosstab(df['Control_type'], df['direction'], margins=True)
    print(ct.to_string())

    # --- Cell line breakdown ---
    print(f"\n{sep}")
    print("STRATIFICATION: CELL LINE")
    print(sep)
    ct = pd.crosstab(df['Cell_line'], df['direction'], margins=True)
    print(ct.to_string())

    # --- Tissue origin breakdown ---
    print(f"\n{sep}")
    print("STRATIFICATION: TISSUE ORIGIN")
    print(sep)
    ct = pd.crosstab(df['Organ'].fillna('unknown'), df['direction'], margins=True)
    print(ct.to_string())

    # --- Treatment type breakdown (top 20) ---
    print(f"\n{sep}")
    print("STRATIFICATION: TOP 20 TREATMENTS")
    print(sep)
    treat_counts = df.groupby('Treatment').agg(
        n_prompts=('direction', 'size'),
        n_up=('direction', lambda x: (x == 'upregulated').sum()),
        n_down=('direction', lambda x: (x == 'downregulated').sum()),
        n_nc=('direction', lambda x: (x == 'no_change').sum()),
        n_genes=('Gene', 'nunique'),
    ).sort_values('n_prompts', ascending=False).head(20)
    print(treat_counts.to_string())

    # --- Gene frequency (top 20 most queried genes) ---
    print(f"\n{sep}")
    print("STRATIFICATION: TOP 20 QUERIED GENES")
    print(sep)
    gene_counts = df.groupby('Gene').agg(
        n_prompts=('direction', 'size'),
        n_up=('direction', lambda x: (x == 'upregulated').sum()),
        n_down=('direction', lambda x: (x == 'downregulated').sum()),
        n_nc=('direction', lambda x: (x == 'no_change').sum()),
        n_comparisons=('Comparison', 'nunique'),
    ).sort_values('n_prompts', ascending=False).head(20)
    print(gene_counts.to_string())

    # --- Accession coverage (top 15) ---
    print(f"\n{sep}")
    print("STRATIFICATION: TOP 15 ACCESSIONS")
    print(sep)
    acc_counts = df.groupby('Acc_no').agg(
        n_prompts=('direction', 'size'),
        n_comparisons=('Comparison', 'nunique'),
        n_treatments=('Treatment', 'nunique'),
        n_genes=('Gene', 'nunique'),
    ).sort_values('n_prompts', ascending=False).head(15)
    print(acc_counts.to_string())

    # --- Timepoint distribution ---
    print(f"\n{sep}")
    print("STRATIFICATION: TIMEPOINTS")
    print(sep)
    time_counts = df['Time_after_induction'].value_counts().sort_index()
    for t, c in time_counts.items():
        print(f"  {str(t):10s}  {c:5d}")

    # --- Prompts per gene histogram ---
    print(f"\n{sep}")
    print("DISTRIBUTION: PROMPTS PER GENE")
    print(sep)
    ppg = df.groupby('Gene').size()
    print(f"  min:    {ppg.min()}")
    print(f"  25th:   {ppg.quantile(0.25):.0f}")
    print(f"  median: {ppg.median():.0f}")
    print(f"  75th:   {ppg.quantile(0.75):.0f}")
    print(f"  max:    {ppg.max()}")
    print(f"  mean:   {ppg.mean():.1f}")

    # --- Prompts per comparison histogram ---
    print(f"\n{sep}")
    print("DISTRIBUTION: PROMPTS PER COMPARISON")
    print(sep)
    ppc = df.groupby('Comparison').size()
    print(f"  min:    {ppc.min()}")
    print(f"  25th:   {ppc.quantile(0.25):.0f}")
    print(f"  median: {ppc.median():.0f}")
    print(f"  75th:   {ppc.quantile(0.75):.0f}")
    print(f"  max:    {ppc.max()}")
    print(f"  mean:   {ppc.mean():.1f}")

    # --- Splitting feasibility ---
    print(f"\n{sep}")
    print("SPLITTING FEASIBILITY (by Acc_no)")
    print(sep)
    acc_sizes = df.groupby('Acc_no').size().sort_values(ascending=False)
    cumulative = acc_sizes.cumsum() / len(df)
    n_80 = (cumulative <= 0.80).sum()
    print(f"  Accessions needed for 80% of prompts: {n_80}")
    print(f"  Remaining accessions for test set:    {len(acc_sizes) - n_80}")
    print(f"  Largest accession: {acc_sizes.index[0]} ({acc_sizes.iloc[0]} prompts, "
          f"{100 * acc_sizes.iloc[0] / len(df):.1f}%)")
    print(f"  Singleton accessions (1 prompt): {(acc_sizes == 1).sum()}")

    print(f"\n{'=' * 60}")
    print("END EDA")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# 5. GENERATE PROMPTS
# ---------------------------------------------------------------------------

def format_senescence_type(sen_type: str, sen_subtype: str) -> str:
    """Human-readable senescence type description."""
    type_map = {
        'OIS': 'oncogene-induced senescence',
        'DDIS': 'DNA damage-induced senescence',
        'REP': 'replicative senescence',
        'dNTP': 'dNTP depletion-induced senescence',
        'OSKM': 'reprogramming-induced senescence',
    }
    base = type_map.get(sen_type, sen_type)
    if sen_subtype and sen_subtype != 'none' and sen_subtype != sen_type:
        return f"{base} ({sen_subtype})"
    return base


# Known small-molecule drugs — used in format_treatment and _experiment_xml
# to suppress gene_context blocks that don't apply to drug perturbations.
KNOWN_DRUGS = {
    'rapamycin', 'rotenone', 'digoxin', 'ouabain', 'JQ1', 'TSA', 'ARV825',
    'CCCP', 'Celecoxib', 'digoxin_caspase_inhibitor', 'clobetasol',
    'ouabain_caspase_inhibitor', '3deazaadenosine', 'compoundA',
    'Y27632', 'KU60019', 'Y27632_KU60019',
}


def format_treatment(treatment: str, treatment_dose: str,
                     gene_down: str = 'none', gene_up: str = 'none') -> str:
    """Human-readable treatment description.
    
    Derives the method (siRNA, shRNA, CRISPR, drug, etc.) from the Treatment
    column, but uses Gene_down/Gene_up as the canonical target name to avoid
    alias issues (e.g. siJUN1 -> JUN, JQ1 -> BRD4).
    """
    # Canonical target: prefer Gene_down/Gene_up over parsing treatment name
    target = None
    if gene_down not in ('none', 'nan', ''):
        target = gene_down
    elif gene_up not in ('none', 'nan', ''):
        target = gene_up

    # Known small molecules / drugs — use drug name + target
    # Determine method from treatment naming convention
    if treatment in KNOWN_DRUGS:
        if target:
            desc = f"treatment with {treatment} (targeting {target})"
        else:
            desc = f"treatment with {treatment}"
    elif treatment.startswith('si'):
        desc = f"siRNA knockdown of {target or treatment[2:]}"
    elif treatment.startswith(('sh', 'Sh')):
        desc = f"shRNA knockdown of {target or treatment[2:]}"
    elif 'sh' in treatment.lower() and 'pLKO' in treatment:
        desc = f"shRNA knockdown of {target or treatment.split('sh')[-1]}"
    elif treatment.endswith('_CRISPR'):
        desc = f"CRISPR knockout of {target or treatment.replace('_CRISPR', '')}"
    elif treatment.endswith('_OE'):
        desc = f"overexpression of {target or treatment.replace('_OE', '')}"
    elif treatment.startswith('LNA'):
        desc = f"LNA antisense inhibition of {target or treatment.replace('LNA', '')}"
    elif target and gene_down not in ('none', 'nan', '') and gene_up in ('none', 'nan', ''):
        desc = f"knockdown of {target}"
    elif target and gene_up not in ('none', 'nan', '') and gene_down in ('none', 'nan', ''):
        desc = f"overexpression of {target}"
    else:
        desc = f"treatment with {treatment}"

    if treatment_dose and treatment_dose not in ('none', 'nan', ''):
        desc += f" at dose {treatment_dose}"
    return desc


def format_tissue(organ: str, cell_line: str) -> str:
    """Human-readable tissue/cell line description."""
    cell_line_map = {
        'IMR': 'IMR-90',
        'WI38': 'WI-38',
        'MRC': 'MRC-5',
        'MRC5': 'MRC-5',
        'Tig3': 'TIG-3',
        'FL2': 'FL2',
    }
    name = cell_line_map.get(cell_line, cell_line)
    if organ and organ != 'none' and not pd.isna(organ):
        return f"{name} {organ.lower()} fibroblasts"
    return f"{name} fibroblasts"


def format_control(control_type: str) -> str:
    """Human-readable control condition."""
    control_map = {
        'OIS': 'untreated oncogene-induced senescent cells',
        'DDIS': 'untreated DNA damage-induced senescent cells',
        'REP': 'untreated replicatively senescent cells',
    }
    return control_map.get(control_type, f'untreated {control_type} cells')


# ---------------------------------------------------------------------------
# 5a. SPLIT BALANCED SET INTO THREE TASK PARTITIONS
# ---------------------------------------------------------------------------

def split_three_way(
    df: pd.DataFrame,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split balanced data into three partitions for different task formats.
    Stratifies by direction to maintain class balance within each partition.

    Pairwise gets a larger share (50%) because the |LogFC| gap filter drops
    many candidate pairs. MCQ and regression each get 25%.

    Returns: (mcq_df, pairwise_df, regression_df)
    """
    rng = np.random.RandomState(random_state)
    mcq_parts, pair_parts, reg_parts = [], [], []

    for direction in ['upregulated', 'downregulated', 'no_change']:
        pool = df[df['direction'] == direction].copy()
        pool = pool.sample(frac=1, random_state=rng).reset_index(drop=True)

        n = len(pool)
        split1 = n // 4           # 25% MCQ
        split2 = split1 + n // 2  # 50% pairwise
        # remaining ~25% regression

        mcq_parts.append(pool.iloc[:split1])
        pair_parts.append(pool.iloc[split1:split2])
        reg_parts.append(pool.iloc[split2:])

    mcq_df = pd.concat(mcq_parts, ignore_index=True).sample(frac=1, random_state=rng).reset_index(drop=True)
    pair_df = pd.concat(pair_parts, ignore_index=True).sample(frac=1, random_state=rng).reset_index(drop=True)
    reg_df = pd.concat(reg_parts, ignore_index=True).sample(frac=1, random_state=rng).reset_index(drop=True)

    print(f"\nThree-way split:")
    print(f"  MCQ partition:        {len(mcq_df)} rows")
    print(f"  Pairwise partition:   {len(pair_df)} rows")
    print(f"  Regression partition: {len(reg_df)} rows")

    for name, part in [('MCQ', mcq_df), ('Pairwise', pair_df), ('Regression', reg_df)]:
        counts = part['direction'].value_counts()
        print(f"  {name} label balance: { {k: int(v) for k, v in counts.items()} }")

    return mcq_df, pair_df, reg_df


# ---------------------------------------------------------------------------
# 5b. SHARED HELPERS
# ---------------------------------------------------------------------------

SYSTEM_MSG = (
    'You are a biomedical AI specialized in aging biology and cellular senescence, '
    'trained on genomic, transcriptomic, and epigenomic data.'
)


def _build_experiment_block(row: pd.Series) -> tuple[str, str, str, str, str, str]:
    """Return (cell_desc, sen_desc, treat_desc, control_desc, time_str, assay)."""
    cell_desc = format_tissue(row.get('Organ', ''), row['Cell_line'])
    sen_desc = format_senescence_type(row['Sen_type'], row.get('Sen_subtype', ''))
    treat_desc = format_treatment(
        row['Treatment'],
        str(row.get('Treatment_dose', 'none')),
        gene_down=str(row.get('Gene_down', 'none')),
        gene_up=str(row.get('Gene_up', 'none')),
    )
    control_desc = format_control(row['Control_type'])

    time_str = ''
    if pd.notna(row.get('Time_after_induction')) and row['Time_after_induction'] != 'none':
        time_str = f" at {row['Time_after_induction']} post-senescence induction"

    assay = 'RNA-seq' if row.get('RNAseq_Microarray') == 'R' else 'microarray'
    return cell_desc, sen_desc, treat_desc, control_desc, time_str, assay


def _gene_display(row: pd.Series) -> str:
    gene = row['Gene']
    gene_name = str(row.get('cellage_gene_name', ''))
    if gene_name and gene_name != 'nan':
        return f"{gene} ({gene_name})"
    return gene


def _experiment_xml(row: pd.Series, cell_desc: str, sen_desc: str,
                    treat_desc: str, control_desc: str) -> str:
    """Build the <experiment> and optional <gene_context> XML blocks."""
    experiment = (
        f"Cell line: {cell_desc}. "
        f"Senescence model: {sen_desc}. "
        f"Perturbation: {treat_desc}. "
        f"Control condition: {control_desc}."
    )
    if pd.notna(row.get('Replicates')):
        experiment += f" Biological replicates: {int(row['Replicates'])}."
    analysis = str(row.get('Analysis', ''))
    if analysis and analysis != 'nan':
        experiment += f" Differential expression analysis: {analysis}."

    gene_down = str(row.get('Gene_down', 'none'))
    gene_up = str(row.get('Gene_up', 'none'))
    gene_context_parts = []
    if gene_down not in ('none', 'nan', ''):
        gene_context_parts.append(f"knocked down gene(s): {gene_down}")
    if gene_up not in ('none', 'nan', ''):
        gene_context_parts.append(f"overexpressed gene(s): {gene_up}")

    xml = f"<experiment>\n{experiment}\n</experiment>"
    if gene_context_parts:
        gc = "In this experiment, " + ", ".join(gene_context_parts) + "."
        xml += f"\n<gene_context>\n{gc}\n</gene_context>"
    return xml


def _build_follow_up(row: pd.Series, gene_display: str) -> str:
    gene = row['Gene']
    logfc = round(float(row['LogFC']), 4)
    pval = float(row['Pvalues'])
    pmid = str(row.get('cellage_pmid', ''))
    accession = row['Acc_no']
    cellage_effect = str(row.get('cellage_senescence_effect', ''))
    cellage_sen_type = str(row.get('cellage_senescence_type', ''))

    cellage_block = f"According to CellAge, {gene} {cellage_effect.lower()} cellular senescence"
    if cellage_sen_type and cellage_sen_type not in ('nan', 'Unclear', 'none'):
        cellage_block += f" (senescence type: {cellage_sen_type})"
    cellage_block += "."

    fu = (f"Gene: {gene_display}. Log2FC={logfc}, p={pval:.2e}. "
          f"Significance threshold: |Log2FC| > 1.0, pval < 0.05. "
          f"GEO accession: {accession}. {cellage_block}")
    if pmid and pmid != 'nan':
        fu += f" CellAge PMID: {pmid}."
    return fu


def _build_metadata_dict(row: pd.Series, follow_up: str, assay: str) -> dict:
    gene = row['Gene']
    gene_name = str(row.get('cellage_gene_name', ''))
    return {
        'follow_up': follow_up,
        'gene': gene,
        'gene_name': gene_name if gene_name != 'nan' else '',
        'logfc': round(float(row['LogFC']), 4),
        'pvalue': float(row['Pvalues']),
        'treatment': row['Treatment'],
        'treatment_dose': str(row.get('Treatment_dose', 'none')),
        'senescence_type': row['Sen_type'],
        'senescence_subtype': str(row.get('Sen_subtype', 'none')),
        'control_type': row['Control_type'],
        'cell_line': row['Cell_line'],
        'organ': str(row.get('Organ', 'none')),
        'timepoint': str(row.get('Time_after_induction', 'none')),
        'accession': row['Acc_no'],
        'comparison': row['Comparison'],
        'study': str(row.get('Study', 'none')),
        'cellage_effect': str(row.get('cellage_senescence_effect', '')),
        'cellage_senescence_type': str(row.get('cellage_senescence_type', '')),
        'cellage_pmid': str(row.get('cellage_pmid', '')) if str(row.get('cellage_pmid', '')) != 'nan' else '',
        'assay': assay,
    }


# ---------------------------------------------------------------------------
# 5c. MCQ PROMPT GENERATOR (unchanged logic)
# ---------------------------------------------------------------------------

def generate_mcq_prompt(row: pd.Series, lb_id_counter: int) -> dict:
    """Generate a single MCQ benchmark row."""
    cell_desc, sen_desc, treat_desc, control_desc, time_str, assay = _build_experiment_block(row)
    gd = _gene_display(row)

    direction_letter = {'upregulated': 'A', 'downregulated': 'B', 'no_change': 'C'}[row['direction']]

    question = (
        f"You are presented with a senescence perturbation experiment. "
        f"In {cell_desc} undergoing {sen_desc}{time_str}, "
        f"{treat_desc} is applied. "
        f"Compared to {control_desc}, the mRNA expression of "
        f"{gd} measured by {assay}:"
    )
    options = "A. increases (upregulated) B. decreases (downregulated) C. no significant change"

    user_content = (
        f"<question>\n{question}\n</question>\n"
        f"<options>\n{options}\n</options>\n"
        + _experiment_xml(row, cell_desc, sen_desc, treat_desc, control_desc)
    )

    follow_up = _build_follow_up(row, gd)

    messages = [
        {'role': 'system', 'content': SYSTEM_MSG},
        {'role': 'user', 'content': user_content},
        {'role': 'assistant', 'content': direction_letter},
    ]

    return {
        'lb_id': f'LB-SEN-MCQ-{lb_id_counter:04d}',
        'pool': 'senescence_perturbation_mcq',
        'display_name': 'Senescence Perturbation / MCQ',
        'display_group': 'Senescence Perturbation',
        'domain': 'transcriptomics',
        'format': 'mcq',
        'metric': 'accuracy',
        'units': 'direction',
        'messages': messages,
        'task': 'senescence_perturbation_mcq',
        'has_reasoning': False,
        'metadata': json.dumps({**_build_metadata_dict(row, follow_up, assay)}),
    }


# ---------------------------------------------------------------------------
# 5d. PAIRWISE PROMPT GENERATOR
# ---------------------------------------------------------------------------

def build_pairwise_pairs(
    df: pd.DataFrame,
    min_logfc_gap: float = 0.5,
    random_state: int = 42,
) -> list[tuple[pd.Series, pd.Series]]:
    """
    Build pairwise comparisons from rows in the same Comparison (same experiment).
    Each pair contrasts two genes with different magnitudes of expression change.
    We pair rows within the same comparison so the experimental context is shared.

    Only pairs whose ||LogFC_A| - |LogFC_B|| >= min_logfc_gap are kept, so there
    is always a clear winner (no "approximately equal" option).

    Strategy: for each comparison, pair genes with the largest |LogFC| difference.
    Capped at 3 pairs per comparison to keep diversity high.
    """
    rng = np.random.RandomState(random_state)
    pairs = []
    skipped = 0

    for comp, group in df.groupby('Comparison'):
        if len(group) < 2:
            continue
        # Sort by absolute LogFC, pair highest with lowest
        sorted_g = group.sort_values('LogFC', key=lambda x: x.abs(), ascending=False)
        rows = list(sorted_g.iterrows())

        # Pair first with last, second with second-to-last, etc.
        n_candidates = len(rows) // 2
        kept = 0
        for i in range(n_candidates):
            if kept >= 3:
                break
            row_a = rows[i][1]
            row_b = rows[-(i + 1)][1]
            gap = abs(abs(float(row_a['LogFC'])) - abs(float(row_b['LogFC'])))
            if gap < min_logfc_gap:
                skipped += 1
                continue
            # Randomly order A/B to prevent position bias
            if rng.random() > 0.5:
                pairs.append((row_a, row_b))
            else:
                pairs.append((row_b, row_a))
            kept += 1

    rng.shuffle(pairs)
    print(f"  Built {len(pairs)} pairwise pairs from {df['Comparison'].nunique()} comparisons "
          f"(min |LogFC| gap = {min_logfc_gap}, {skipped} pairs skipped below threshold)")
    return pairs


def generate_pairwise_prompt(
    row_a: pd.Series,
    row_b: pd.Series,
    lb_id_counter: int,
) -> dict:
    """
    Generate a binary pairwise comparison prompt: given two genes in the same
    experiment, which one shows a larger absolute expression change?
    Pairs are pre-filtered to have a minimum |LogFC| gap, so there is always
    a clear winner.
    """
    # Both rows share the same comparison, so experiment context is the same
    cell_desc, sen_desc, treat_desc, control_desc, time_str, assay = _build_experiment_block(row_a)
    gd_a = _gene_display(row_a)
    gd_b = _gene_display(row_b)

    abs_a = abs(float(row_a['LogFC']))
    abs_b = abs(float(row_b['LogFC']))
    # Ground truth: which gene has the larger absolute change?
    answer = 'A' if abs_a > abs_b else 'B'

    question = (
        f"In a senescence perturbation experiment using {cell_desc} undergoing "
        f"{sen_desc}{time_str}, {treat_desc} is applied. "
        f"Compared to {control_desc}, consider the following two genes measured by {assay}:\n\n"
        f"Gene A: {gd_a}\n"
        f"Gene B: {gd_b}\n\n"
        f"Which gene shows a larger absolute change in mRNA expression (|Log2FC|)?"
    )

    options = "A. Gene A shows a larger absolute change B. Gene B shows a larger absolute change"

    user_content = (
        f"<question>\n{question}\n</question>\n"
        f"<options>\n{options}\n</options>\n"
        + _experiment_xml(row_a, cell_desc, sen_desc, treat_desc, control_desc)
    )

    logfc_a = round(float(row_a['LogFC']), 4)
    logfc_b = round(float(row_b['LogFC']), 4)
    pval_a = float(row_a['Pvalues'])
    pval_b = float(row_b['Pvalues'])

    follow_up = (
        f"Gene A: {gd_a}, Log2FC={logfc_a}, p={pval_a:.2e}. "
        f"Gene B: {gd_b}, Log2FC={logfc_b}, p={pval_b:.2e}. "
        f"|Log2FC_A|={abs_a:.4f}, |Log2FC_B|={abs_b:.4f}. "
        f"GEO accession: {row_a['Acc_no']}."
    )

    messages = [
        {'role': 'system', 'content': SYSTEM_MSG},
        {'role': 'user', 'content': user_content},
        {'role': 'assistant', 'content': answer},
    ]

    metadata = {
        'follow_up': follow_up,
        'gene_a': row_a['Gene'],
        'gene_b': row_b['Gene'],
        'logfc_a': logfc_a,
        'logfc_b': logfc_b,
        'pvalue_a': pval_a,
        'pvalue_b': pval_b,
        'abs_logfc_a': round(abs_a, 4),
        'abs_logfc_b': round(abs_b, 4),
        'direction_a': row_a['direction'],
        'direction_b': row_b['direction'],
        'treatment': row_a['Treatment'],
        'senescence_type': row_a['Sen_type'],
        'control_type': row_a['Control_type'],
        'cell_line': row_a['Cell_line'],
        'timepoint': str(row_a.get('Time_after_induction', 'none')),
        'accession': row_a['Acc_no'],
        'comparison': row_a['Comparison'],
        'assay': assay,
    }

    return {
        'lb_id': f'LB-SEN-PAIR-{lb_id_counter:04d}',
        'pool': 'senescence_perturbation_pairwise',
        'display_name': 'Senescence Perturbation / Pairwise',
        'display_group': 'Senescence Perturbation',
        'domain': 'transcriptomics',
        'format': 'binary',
        'metric': 'accuracy',
        'units': 'direction',
        'messages': messages,
        'task': 'senescence_perturbation_pairwise',
        'has_reasoning': False,
        'metadata': json.dumps(metadata),
    }


# ---------------------------------------------------------------------------
# 5e. REGRESSION PROMPT GENERATOR (predict Log2FC)
# ---------------------------------------------------------------------------

def generate_regression_prompt(row: pd.Series, lb_id_counter: int, logfc_cap: float = 10.0) -> dict:
    """
    Generate a regression prompt: predict the Log2FC value for a named gene
    under a specific perturbation. The model must output a numeric value.
    Ground truth LogFC is capped to [-logfc_cap, logfc_cap].
    """
    cell_desc, sen_desc, treat_desc, control_desc, time_str, assay = _build_experiment_block(row)
    gd = _gene_display(row)
    logfc_raw = round(float(row['LogFC']), 4)
    logfc = round(np.clip(logfc_raw, -logfc_cap, logfc_cap), 4)

    question = (
        f"You are presented with a senescence perturbation experiment. "
        f"In {cell_desc} undergoing {sen_desc}{time_str}, "
        f"{treat_desc} is applied. "
        f"Compared to {control_desc}, predict the Log2 fold-change (Log2FC) "
        f"in mRNA expression of {gd} measured by {assay}. "
        f"Respond with only a numeric value rounded to two decimal places "
        f"(positive = upregulated, negative = downregulated)."
    )

    user_content = (
        f"<question>\n{question}\n</question>\n"
        + _experiment_xml(row, cell_desc, sen_desc, treat_desc, control_desc)
    )

    follow_up = _build_follow_up(row, gd)

    messages = [
        {'role': 'system', 'content': SYSTEM_MSG},
        {'role': 'user', 'content': user_content},
        {'role': 'assistant', 'content': str(round(logfc, 2))},
    ]

    return {
        'lb_id': f'LB-SEN-REG-{lb_id_counter:04d}',
        'pool': 'senescence_perturbation_regression',
        'display_name': 'Senescence Perturbation / Regression',
        'display_group': 'Senescence Perturbation',
        'domain': 'transcriptomics',
        'format': 'regression',
        'metric': 'mae',
        'units': 'log2fc',
        'messages': messages,
        'task': 'senescence_perturbation_regression',
        'has_reasoning': False,
        'metadata': json.dumps({**_build_metadata_dict(row, follow_up, assay)}),
    }


# ---------------------------------------------------------------------------
# 6. GENERATE ALL BENCHMARKS
# ---------------------------------------------------------------------------

def _sample_tissue_balanced(
    df: pd.DataFrame,
    n: int,
    rng: np.random.RandomState,
    organ_col: str = 'Organ',
) -> pd.DataFrame:
    """
    Sample n rows from df with equal representation across tissue types.
    If a tissue has fewer rows than its equal share, takes all of them and
    redistributes the remainder to tissues with capacity.
    """
    tissues = df[organ_col].unique()
    n_tissues = len(tissues)
    if n_tissues <= 1:
        return df.sample(min(n, len(df)), random_state=rng)

    target_per_tissue = n // n_tissues
    remainder = n - target_per_tissue * n_tissues

    parts = []
    shortfall = 0
    capacity = []  # (tissue, surplus_rows)

    for tissue in tissues:
        pool = df[df[organ_col] == tissue]
        alloc = target_per_tissue
        if len(pool) >= alloc:
            parts.append(pool.sample(alloc, random_state=rng))
            if len(pool) > alloc:
                capacity.append((tissue, pool, len(pool) - alloc))
        else:
            parts.append(pool)
            shortfall += alloc - len(pool)

    # Distribute remainder + shortfall from tissues with capacity
    extra_needed = remainder + shortfall
    for tissue, pool, surplus in capacity:
        if extra_needed <= 0:
            break
        already_sampled = next(p for p in parts if (p[organ_col] == tissue).all())
        extra = min(extra_needed, surplus)
        already_used = set(already_sampled.index)
        pool_remaining = pool[~pool.index.isin(already_used)]
        parts.append(pool_remaining.sample(extra, random_state=rng))
        extra_needed -= extra

    result = pd.concat(parts).sample(frac=1, random_state=rng)
    return result


def generate_all_benchmarks(
    mcq_df: pd.DataFrame,
    pair_df: pd.DataFrame,
    reg_df: pd.DataFrame,
    target_per_task: int = 100,
    min_logfc_gap: float = 0.5,
    logfc_cap: float = 10.0,
    random_state: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Generate prompts for all three task formats, capped to target_per_task each,
    with tissue-balanced sampling across Organ types."""
    rng = np.random.RandomState(random_state)

    # --- MCQ: tissue-balanced sample from input df before generating ---
    mcq_input = _sample_tissue_balanced(mcq_df, target_per_task, rng)
    mcq_prompts = []
    for i, (_, row) in enumerate(mcq_input.iterrows()):
        mcq_prompts.append(generate_mcq_prompt(row, i + 1))
    tissue_counts = mcq_input['Organ'].value_counts().to_dict()
    print(f"  MCQ prompts: {len(mcq_prompts)} (target {target_per_task}) | tissues: {tissue_counts}")

    # --- Pairwise: build all pairs, then tissue-balance at selection ---
    pairs = build_pairwise_pairs(pair_df, min_logfc_gap=min_logfc_gap, random_state=random_state)

    # Attach tissue to each pair (from row_a, which shares context with row_b)
    pair_df_idx = pd.DataFrame({
        'Organ': [row_a.get('Organ', 'unknown') for row_a, _ in pairs],
        'pair_idx': range(len(pairs)),
    })

    # Shuffle within each tissue first
    tissues = pair_df_idx['Organ'].unique()
    tissue_pools = {}
    for tissue in tissues:
        idxs = pair_df_idx[pair_df_idx['Organ'] == tissue]['pair_idx'].tolist()
        rng.shuffle(idxs)
        tissue_pools[tissue] = idxs

    # Soft balance: allocate equally, but let tissues with surplus fill shortfalls
    target_per_tissue = target_per_task // len(tissues)
    allocated = {t: min(target_per_tissue, len(pool)) for t, pool in tissue_pools.items()}
    shortfall = sum(target_per_tissue - allocated[t] for t in tissues)
    total_allocated = sum(allocated.values())

    # Distribute shortfall + integer-division remainder to tissues with spare capacity
    still_needed = target_per_task - total_allocated
    for tissue in sorted(tissues, key=lambda t: len(tissue_pools[t]), reverse=True):
        if still_needed <= 0:
            break
        spare = len(tissue_pools[tissue]) - allocated[tissue]
        take = min(still_needed, spare)
        allocated[tissue] += take
        still_needed -= take

    selected_pair_idxs = []
    tissue_pair_counts = {}
    for tissue in tissues:
        idxs = tissue_pools[tissue][:allocated[tissue]]
        selected_pair_idxs.extend(idxs)
        tissue_pair_counts[tissue] = len(idxs)

    rng.shuffle(selected_pair_idxs)

    pair_prompts = []
    for i, idx in enumerate(selected_pair_idxs):
        row_a, row_b = pairs[idx]
        pair_prompts.append(generate_pairwise_prompt(row_a, row_b, i + 1))

    print(f"  Pairwise prompts: {len(pair_prompts)} (target {target_per_task}) | tissues: {tissue_pair_counts}")
    if len(pair_prompts) < target_per_task:
        print(f"    ⚠ Below target — only {len(pairs)} valid pairs survived the "
              f"|LogFC| gap ≥ {min_logfc_gap} filter")

    # --- Regression: tissue-balanced sample from input df before generating ---
    reg_input = _sample_tissue_balanced(reg_df, target_per_task, rng)
    reg_prompts = []
    for i, (_, row) in enumerate(reg_input.iterrows()):
        reg_prompts.append(generate_regression_prompt(row, i + 1, logfc_cap=logfc_cap))
    tissue_counts = reg_input['Organ'].value_counts().to_dict()
    print(f"  Regression prompts: {len(reg_prompts)} (target {target_per_task}) | tissues: {tissue_counts}")

    return mcq_prompts, pair_prompts, reg_prompts


# ---------------------------------------------------------------------------
# 7. SUMMARY STATISTICS
# ---------------------------------------------------------------------------

def compute_summary(
    mcq_prompts: list[dict],
    pair_prompts: list[dict],
    reg_prompts: list[dict],
) -> dict:
    """Compute benchmark summary statistics across all task formats."""

    def _pool_stats(prompts: list[dict], fmt: str) -> dict:
        if not prompts:
            return {'total': 0}
        metadata_list = [json.loads(p['metadata']) for p in prompts]
        meta = pd.DataFrame(metadata_list)
        labels = [p['messages'][-1]['content'] for p in prompts]
        stats = {
            'total_prompts': len(prompts),
            'format': fmt,
            'label_distribution': {k: int(v) for k, v in pd.Series(labels).value_counts().items()},
            'unique_genes': int(meta.get('gene', meta.get('gene_a', pd.Series())).nunique())
                if 'gene' in meta.columns else int(meta['gene_a'].nunique()),
            'unique_treatments': int(meta['treatment'].nunique()),
            'unique_accessions': int(meta['accession'].nunique()),
            'unique_cell_lines': int(meta['cell_line'].nunique()),
        }
        if 'senescence_type' in meta.columns:
            stats['unique_senescence_types'] = int(meta['senescence_type'].nunique())
        return stats

    all_prompts = mcq_prompts + pair_prompts + reg_prompts

    summary = {
        'total_prompts': len(all_prompts),
        'mcq': _pool_stats(mcq_prompts, 'mcq'),
        'pairwise': _pool_stats(pair_prompts, 'pairwise'),
        'regression': _pool_stats(reg_prompts, 'regression'),
        'thresholds': {
            'logfc': 1.0,
            'pvalue': 0.05,
            'pairwise_min_logfc_gap': 0.5,
            'logfc_cap': 10.0,
            'target_per_task': 100,
        },
        'splitting_recommendation': (
            'Split by accession (GEO accession) to prevent data leakage. '
            'All prompts from a given study go into either train or test.'
        ),
    }
    return summary


# ---------------------------------------------------------------------------
# 8. TRAIN / TEST SPLIT BY ACCESSION
# ---------------------------------------------------------------------------

def split_train_test_by_accession(
    prompts: list[dict],
    test_fraction: float = 0.20,
    random_state: int = 42,
) -> tuple[list[dict], list[dict], dict]:
    """
    Split prompts into train/test sets by GEO accession to prevent data leakage.

    All prompts from a given accession go entirely into train or test.
    Accessions are greedily assigned to the test set (smallest first) until
    the target test fraction is reached, ensuring diversity in the test set
    rather than dumping a single large accession into it.

    Returns: (train_prompts, test_prompts, split_report)
    """
    rng = np.random.RandomState(random_state)

    # Extract accession from metadata for each prompt
    accession_map = {}  # accession -> list of prompt indices
    treatment_map = {}  # accession -> set of treatments
    for i, p in enumerate(prompts):
        meta = json.loads(p['metadata'])
        acc = meta.get('accession', meta.get('accession', ''))
        treat = meta.get('treatment', meta.get('treatment', ''))
        accession_map.setdefault(acc, []).append(i)
        treatment_map.setdefault(acc, set()).add(treat)

    # Sort accessions by prompt count (ascending) for greedy test fill
    acc_sizes = {acc: len(idxs) for acc, idxs in accession_map.items()}
    sorted_accs = sorted(acc_sizes.keys(), key=lambda a: acc_sizes[a])

    # Shuffle within same-size groups for randomness
    size_groups = {}
    for acc in sorted_accs:
        size_groups.setdefault(acc_sizes[acc], []).append(acc)
    shuffled_accs = []
    for size in sorted(size_groups.keys()):
        group = size_groups[size]
        rng.shuffle(group)
        shuffled_accs.extend(group)

    total = len(prompts)
    target_test = int(total * test_fraction)

    test_accs = set()
    test_count = 0
    for acc in shuffled_accs:
        if test_count >= target_test:
            break
        test_accs.add(acc)
        test_count += acc_sizes[acc]

    train_accs = set(accession_map.keys()) - test_accs

    # Build train/test prompt lists
    test_idxs = set()
    for acc in test_accs:
        test_idxs.update(accession_map[acc])
    train_prompts = [p for i, p in enumerate(prompts) if i not in test_idxs]
    test_prompts = [p for i, p in enumerate(prompts) if i in test_idxs]

    # Add split label to each prompt's metadata
    for p in train_prompts:
        meta = json.loads(p['metadata'])
        meta['split'] = 'train'
        p['metadata'] = json.dumps(meta)
    for p in test_prompts:
        meta = json.loads(p['metadata'])
        meta['split'] = 'test'
        p['metadata'] = json.dumps(meta)

    # Check treatment leakage
    train_treatments = set()
    for acc in train_accs:
        train_treatments.update(treatment_map[acc])
    test_treatments = set()
    for acc in test_accs:
        test_treatments.update(treatment_map[acc])
    leaked_treatments = train_treatments & test_treatments

    # Build split report
    report = {
        'train_accessions': sorted(train_accs),
        'test_accessions': sorted(test_accs),
        'n_train_accessions': len(train_accs),
        'n_test_accessions': len(test_accs),
        'n_train_prompts': len(train_prompts),
        'n_test_prompts': len(test_prompts),
        'actual_test_fraction': round(len(test_prompts) / total, 4),
        'treatment_leakage': {
            'n_leaked': len(leaked_treatments),
            'leaked_treatments': sorted(leaked_treatments),
            'n_train_only': len(train_treatments - test_treatments),
            'n_test_only': len(test_treatments - train_treatments),
        },
    }

    # Print report
    print(f"\n  Train/Test split by accession:")
    print(f"    Train: {len(train_prompts)} prompts from {len(train_accs)} accessions")
    print(f"    Test:  {len(test_prompts)} prompts from {len(test_accs)} accessions")
    print(f"    Actual test fraction: {report['actual_test_fraction']:.1%}")

    # Label balance per split
    for name, subset in [('Train', train_prompts), ('Test', test_prompts)]:
        labels = [p['messages'][-1]['content'] for p in subset]
        counts = pd.Series(labels).value_counts().to_dict()
        print(f"    {name} label balance: {counts}")

    # Format balance per split
    for name, subset in [('Train', train_prompts), ('Test', test_prompts)]:
        formats = pd.Series([p['format'] for p in subset]).value_counts().to_dict()
        print(f"    {name} format balance: {formats}")

    if leaked_treatments:
        print(f"    ⚠ Treatment leakage: {len(leaked_treatments)} treatments appear in both splits")
        if len(leaked_treatments) <= 10:
            print(f"      Leaked: {sorted(leaked_treatments)}")
        else:
            print(f"      Leaked (first 10): {sorted(leaked_treatments)[:10]}...")
    else:
        print(f"    ✓ No treatment leakage across splits")

    return train_prompts, test_prompts, report


# ---------------------------------------------------------------------------
# 9. SAVE HELPERS
# ---------------------------------------------------------------------------

def save_prompts(prompts: list[dict], parquet_path: str, json_path: str) -> None:
    """Save prompts as both parquet and JSON."""
    # --- Parquet ---
    prompts_df = pd.DataFrame(prompts)
    prompts_df['messages'] = prompts_df['messages'].apply(json.dumps)
    prompts_df.to_parquet(parquet_path, index=False)
    print(f"  Parquet saved: {parquet_path} ({len(prompts_df)} rows)")

    # --- JSON ---
    with open(json_path, 'w') as f:
        json.dump(prompts, f, indent=2)
    print(f"  JSON saved:    {json_path} ({len(prompts)} entries)")


# ---------------------------------------------------------------------------
# 10. MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Senescence Perturbation Benchmark Pipeline')
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to the senescence transcriptome CSV')
    parser.add_argument('--cellage', type=str, required=True,
                        help='Path to cellage3.tsv')
    parser.add_argument('--output-dir', type=str, default='.',
                        help='Output directory for all benchmark files')
    parser.add_argument('--summary-output', type=str, default='task_a_senescence_summary.json',
                        help='Output path for benchmark summary JSON')
    parser.add_argument('--balanced-output', type=str, default='task_a_senescence_balanced.csv',
                        help='Output path for balanced subsampled dataset CSV')
    parser.add_argument('--logfc-threshold', type=float, default=1.0,
                        help='Absolute LogFC threshold for significance')
    parser.add_argument('--pvalue-threshold', type=float, default=0.05,
                        help='P-value threshold for significance')
    parser.add_argument('--max-per-gene', type=int, default=3,
                        help='Max prompts per gene per direction')
    parser.add_argument('--max-per-comparison', type=int, default=5,
                        help='Max prompts per comparison per direction')
    parser.add_argument('--min-logfc-gap', type=float, default=0.5,
                        help='Minimum |LogFC| difference between paired genes for pairwise task')
    parser.add_argument('--logfc-cap', type=float, default=10.0,
                        help='Cap ground-truth |LogFC| to this value for regression prompts')
    parser.add_argument('--target-per-task', type=int, default=100,
                        help='Target number of prompts per task format')
    parser.add_argument('--test-fraction', type=float, default=0.20,
                        help='Target fraction of prompts for the test set')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SENESCENCE PERTURBATION BENCHMARK PIPELINE")
    print("  Formats: MCQ + Pairwise + Regression (1/3 each)")
    print("  Split:   80/20 train/test by GEO accession")
    print("=" * 60)

    # Step 1: Load and filter
    print("\n--- Step 1: Load dataset ---")
    df = load_dataset(args.dataset)

    print("\n--- Step 2: Filter to perturbation comparisons ---")
    df = filter_perturbations(df)

    # Step 2: Load CellAge and intersect
    print("\n--- Step 3: Load CellAge ---")
    cellage = load_cellage(args.cellage)

    print("\n--- Step 4: Intersect with CellAge genes ---")
    df = intersect_with_cellage(df, cellage)

    # Step 3: Assign labels
    print("\n--- Step 5: Assign ternary labels ---")
    df = assign_labels(df, args.logfc_threshold, args.pvalue_threshold)

    # Step 4: Subsample
    print("\n--- Step 6: Subsample for balance ---")
    balanced = subsample_balanced(
        df,
        max_per_gene=args.max_per_gene,
        max_per_comparison=args.max_per_comparison,
        random_state=args.seed,
    )

    # Save balanced set
    balanced_path = output_dir / args.balanced_output
    balanced.to_csv(balanced_path, index=False)
    print(f"Balanced dataset saved to: {balanced_path}")

    # Step 5: EDA
    print("\n--- Step 7: Exploratory Data Analysis ---")
    run_eda(balanced)

    # Step 6: Filter to high-significance rows
    print("\n--- Step 8: Filter to high-significance rows ---")
    significant = filter_high_significance(
        balanced,
        target_per_class=args.target_per_task,
        random_state=args.seed,
    )

    # Step 7: Three-way split into task formats
    print("\n--- Step 9: Split into MCQ / Pairwise / Regression ---")
    mcq_df, pair_df, reg_df = split_three_way(significant, random_state=args.seed)

    # Step 8: Generate prompts for all formats
    print("\n--- Step 10: Generate prompts ---")
    mcq_prompts, pair_prompts, reg_prompts = generate_all_benchmarks(
        mcq_df, pair_df, reg_df,
        target_per_task=args.target_per_task,
        min_logfc_gap=args.min_logfc_gap,
        logfc_cap=args.logfc_cap,
        random_state=args.seed,
    )

    # Combine all prompts
    all_prompts = mcq_prompts + pair_prompts + reg_prompts

    # Step 9: Train/test split by accession
    print("\n--- Step 11: Train/Test split by accession ---")
    train_prompts, test_prompts, split_report = split_train_test_by_accession(
        all_prompts,
        test_fraction=args.test_fraction,
        random_state=args.seed,
    )

    # Step 10: Save train/test outputs (parquet + JSON each)
    print("\n--- Step 12: Save outputs ---")
    save_prompts(
        train_prompts,
        str(output_dir / 'task_a_senescence_train.parquet'),
        str(output_dir / 'task_a_senescence_train.json'),
    )
    save_prompts(
        test_prompts,
        str(output_dir / 'task_a_senescence_test.parquet'),
        str(output_dir / 'task_a_senescence_test.json'),
    )

    # Step 11: Summary
    print("\n--- Step 13: Summary ---")
    summary = compute_summary(mcq_prompts, pair_prompts, reg_prompts)
    summary['split'] = split_report
    summary_path = output_dir / args.summary_output
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to: {summary_path}")
    print(f"  Total prompts:       {summary['total_prompts']}")
    print(f"  MCQ prompts:         {summary['mcq']['total_prompts']}")
    print(f"  Pairwise prompts:    {summary['pairwise']['total_prompts']}")
    print(f"  Regression prompts:  {summary['regression']['total_prompts']}")
    print(f"  Train prompts:       {split_report['n_train_prompts']}")
    print(f"  Test prompts:        {split_report['n_test_prompts']}")

    # Print example from each format
    for label, prompts in [('MCQ', mcq_prompts), ('PAIRWISE', pair_prompts), ('REGRESSION', reg_prompts)]:
        if not prompts:
            continue
        ex = prompts[0]
        print(f"\n--- Example {label} prompt ---")
        print(f"lb_id: {ex['lb_id']}")
        print(f"pool: {ex['pool']}")
        print(f"format: {ex['format']}")
        print(f"metric: {ex['metric']}")
        print(f"\n[system]\n{ex['messages'][0]['content']}")
        print(f"\n[user]\n{ex['messages'][1]['content']}")
        print(f"\n[assistant]\n{ex['messages'][2]['content']}")
        meta = json.loads(ex['metadata'])
        print(f"\n[follow_up]\n{meta['follow_up']}")


if __name__ == '__main__':
    main()