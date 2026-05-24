"""
combine_lipidomics.py
---------------------
Combines the MAF lipidomics abundance file with sample-level metadata
(age, diabetes status, gender, individual ID) into a single tidy TSV.

Output format: one row per sample, columns = sample metadata + one column
per lipid (named by metabolite_identification or mass_to_charge if unnamed).

Usage:
    python combine_lipidomics.py \
        --maf  m_MTBLS4461_DI-MS_alternating__metabolite_profiling_v2_maf.tsv \
        --sample s_MTBLS4461.txt \
        --out   combined_lipidomics.tsv

Notes:
- 3 MAF sample columns (LY3227, M151, T82) have no matching metadata entry
  and are dropped with a warning.
- Lipid columns are named by metabolite_identification; duplicates get a
  numeric suffix (_1, _2, …). Rows with a blank/NaN identification fall
  back to "mz_<mass_to_charge>".
- The four unnamed MAF metadata columns (Unnamed: 21-23 + a blank col) are
  dropped; they carry no abundance or annotation data.
"""

import argparse
import sys
import pandas as pd


MAF_FIRST_SAMPLE_COL = 24   # columns 0-23 are lipid metadata; 24+ are samples

SAMPLE_META_COLS = {
    "Sample Name":              "sample_id",
    "Source Name":              "individual_id",
    "Factor Value[Age]":        "age",
    "Factor Value[Gender]":     "gender",
    "Factor Value[Diabetes]":   "diabetes",
}

LIPID_ANNOTATION_COLS = [
    "metabolite_identification",
    "mass_to_charge",
    "charge",
    "database_identifier",
    "chemical_formula",
    "smiles",
]


def load_maf(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", low_memory=False)
    return df


def load_sample(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    keep = [c for c in SAMPLE_META_COLS if c in df.columns]
    missing = [c for c in SAMPLE_META_COLS if c not in df.columns]
    if missing:
        print(f"[WARNING] Sample file missing expected columns: {missing}", file=sys.stderr)
    df = df[keep].rename(columns=SAMPLE_META_COLS)
    return df


def make_lipid_names(maf: pd.DataFrame) -> list[str]:
    """Build unique column names for each lipid row."""
    names = []
    seen: dict[str, int] = {}
    for _, row in maf.iterrows():
        ident = str(row.get("metabolite_identification", "")).strip()
        if not ident or ident.lower() in ("nan", ""):
            mz = row.get("mass_to_charge", "")
            ident = f"mz_{mz}" if mz and str(mz).lower() != "nan" else "unknown"
        base = ident
        if base in seen:
            seen[base] += 1
            ident = f"{base}_{seen[base]}"
        else:
            seen[base] = 0
        names.append(ident)
    return names


def build_combined(maf: pd.DataFrame, sample_meta: pd.DataFrame) -> pd.DataFrame:
    meta_cols = maf.columns[:MAF_FIRST_SAMPLE_COL]
    sample_cols = maf.columns[MAF_FIRST_SAMPLE_COL:].tolist()

    valid_samples = set(sample_meta["sample_id"])
    unmatched = [c for c in sample_cols if c not in valid_samples]
    if unmatched:
        print(
            f"[WARNING] {len(unmatched)} MAF sample column(s) have no metadata — dropping: {unmatched}",
            file=sys.stderr,
        )
    sample_cols = [c for c in sample_cols if c in valid_samples]

    # Abundance sub-matrix: rows=lipids, cols=samples → transpose to rows=samples
    abundance = maf[sample_cols].copy()
    lipid_names = make_lipid_names(maf[list(meta_cols)])
    abundance.index = lipid_names
    abundance_T = abundance.T  # rows=samples, cols=lipids
    abundance_T.index.name = "sample_id"
    abundance_T = abundance_T.reset_index()

    # Merge with sample metadata
    combined = sample_meta.merge(abundance_T, on="sample_id", how="inner")

    n_samples = len(combined)
    n_lipids = len(lipid_names)
    n_no_diabetes = (combined["diabetes"] == "No").sum()
    n_yes_diabetes = (combined["diabetes"] == "Yes").sum()
    print(f"[INFO] Samples merged:  {n_samples}", file=sys.stderr)
    print(f"[INFO] Lipid features:  {n_lipids}", file=sys.stderr)
    print(f"[INFO] Diabetes=No:     {n_no_diabetes}", file=sys.stderr)
    print(f"[INFO] Diabetes=Yes:    {n_yes_diabetes}", file=sys.stderr)
    print(
        f"[INFO] Class imbalance ratio (No/Yes): {n_no_diabetes/max(n_yes_diabetes,1):.2f}",
        file=sys.stderr,
    )

    return combined


def main():
    parser = argparse.ArgumentParser(description="Combine MAF + sample metadata.")
    parser.add_argument("--maf",    required=True, help="Path to the MAF .tsv file")
    parser.add_argument("--sample", required=True, help="Path to the sample .txt file")
    parser.add_argument("--out",    required=True, help="Output combined .tsv path")
    args = parser.parse_args()

    print("[INFO] Loading MAF file …", file=sys.stderr)
    maf = load_maf(args.maf)

    print("[INFO] Loading sample metadata …", file=sys.stderr)
    sample_meta = load_sample(args.sample)

    print("[INFO] Building combined table …", file=sys.stderr)
    combined = build_combined(maf, sample_meta)

    combined.to_csv(args.out, sep="\t", index=False)
    print(f"[INFO] Written → {args.out}  ({combined.shape[0]} rows × {combined.shape[1]} cols)", file=sys.stderr)


if __name__ == "__main__":
    main()