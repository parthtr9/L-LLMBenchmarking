from pathlib import Path
import pandas as pd

# Change this only if your folder is somewhere else
DATASET = "FRANZOSA_IBD_2019"
base = Path("data/processed_data") / DATASET

files = {
    "genera": base / "genera.tsv",
    "metabolites": base / "mtb.tsv",
    "metadata": base / "metadata.tsv",
    "metabolite_map": base / "mtb.map.tsv",
    "species": base / "species.tsv",
}

print(f"\nInspecting dataset: {DATASET}")
print("=" * 80)

# Check which files exist
for name, path in files.items():
    print(f"{name:15} exists: {path.exists()} | {path}")

print("\nLoading core tables...")

genera = pd.read_csv(files["genera"], sep="\t", index_col=0)
metabolites = pd.read_csv(files["metabolites"], sep="\t", index_col=0)

metadata = pd.read_csv(files["metadata"], sep="\t")
metadata = metadata.set_index("Sample")

metabolite_map = pd.read_csv(files["metabolite_map"], sep="\t")

print("\nTable shapes")
print("-" * 80)
print(f"Genera table:       {genera.shape[0]} samples x {genera.shape[1]} genera")
print(f"Metabolite table:   {metabolites.shape[0]} samples x {metabolites.shape[1]} metabolites")
print(f"Metadata table:     {metadata.shape[0]} samples x {metadata.shape[1]} metadata columns")
print(f"Metabolite map:     {metabolite_map.shape[0]} metabolites x {metabolite_map.shape[1]} columns")

# Check shared samples
common_samples = genera.index.intersection(metabolites.index).intersection(metadata.index)

print("\nSample overlap")
print("-" * 80)
print(f"Samples in genera:       {len(genera.index)}")
print(f"Samples in metabolites:  {len(metabolites.index)}")
print(f"Samples in metadata:     {len(metadata.index)}")
print(f"Samples shared by all 3:  {len(common_samples)}")

if len(common_samples) == 0:
    print("\nERROR: No shared samples found across genera, metabolites, and metadata.")
    print("\nFirst 5 genera sample IDs:")
    print(genera.index[:5].tolist())
    print("\nFirst 5 metabolite sample IDs:")
    print(metabolites.index[:5].tolist())
    print("\nFirst 5 metadata sample IDs:")
    print(metadata.index[:5].tolist())
    raise SystemExit

# Subset to common samples
genera = genera.loc[common_samples]
metabolites = metabolites.loc[common_samples]
metadata = metadata.loc[common_samples]

print("\nMetadata columns")
print("-" * 80)
for col in metadata.columns:
    print(col)

print("\nFirst 5 rows of metadata")
print("-" * 80)
print(metadata.head())

print("\nDIRECT CHECK: Study.Group labels")
print("=" * 80)

if "Study.Group" in metadata.columns:
    print(metadata["Study.Group"].value_counts(dropna=False))
else:
    print("Study.Group column not found.")
    print("Available columns:")
    print(metadata.columns.tolist())

print("\nStudy.Group value counts")
print("-" * 80)

if "Study.Group" in metadata.columns:
    print(metadata["Study.Group"].value_counts(dropna=False))
else:
    print("Study.Group column not found.")
    print("Available columns:")
    print(metadata.columns.tolist())

print("\nPotential phenotype/group columns")
print("-" * 80)

keywords = ["group", "disease", "diagnosis", "status", "case", "control", "study"]
candidate_cols = [
    col for col in metadata.columns
    if any(k in col.lower() for k in keywords)
]

if candidate_cols:
    for col in candidate_cols:
        print(f"\nColumn: {col}")
        print(metadata[col].value_counts(dropna=False).head(20))
else:
    print("No obvious phenotype columns found. Inspect metadata manually.")

# Missingness
print("\nMissing values")
print("-" * 80)
print(f"Genera missing values:      {genera.isna().sum().sum()}")
print(f"Metabolites missing values: {metabolites.isna().sum().sum()}")
print(f"Metadata missing values:    {metadata.isna().sum().sum()}")

# Top features for one sample
sample_id = common_samples[0]

print(f"\nExample sample: {sample_id}")
print("-" * 80)

print("\nExample sample metadata")
print("-" * 80)
print(metadata.loc[sample_id])

if "Study.Group" in metadata.columns:
    print("\nExample sample Study.Group")
    print("-" * 80)
    print(metadata.loc[sample_id, "Study.Group"])

print("\nExample sample metadata")
print("-" * 80)
print(metadata.loc[sample_id])

if "Study.Group" in metadata.columns:
    print("\nExample sample Study.Group")
    print("-" * 80)
    print(metadata.loc[sample_id, "Study.Group"])

top_genera = genera.loc[sample_id].sort_values(ascending=False).head(10)

named_metabolites = [
    col for col in metabolites.columns
    if not str(col).endswith(": NA")
]

top_metabolites = (
    metabolites.loc[sample_id, named_metabolites]
    .sort_values(ascending=False)
    .head(10)
)

print("\nTop 10 genera")
print(top_genera)

print("\nTop 10 named metabolites")
print(top_metabolites)