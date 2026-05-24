import math
from pathlib import Path
import json
import random
import pandas as pd

DATASET = "FRANZOSA_IBD_2019"
base = Path("data/processed_data") / DATASET
out_dir = Path("benchmark_prompts")
out_dir.mkdir(exist_ok=True)

N_TOP_GENERA = 10
N_TOP_METABOLITES = 10
RANDOM_SEED = 42
BALANCE_CLASSES = True

random.seed(RANDOM_SEED)

files = {
    "genera": base / "genera.tsv",
    "metabolites": base / "mtb.tsv",
    "metadata": base / "metadata.tsv",
}

genera = pd.read_csv(files["genera"], sep="\t", index_col=0)
metabolites = pd.read_csv(files["metabolites"], sep="\t", index_col=0)

metadata = pd.read_csv(files["metadata"], sep="\t")
metadata = metadata.set_index("Sample")

common_samples = genera.index.intersection(metabolites.index).intersection(metadata.index)

genera = genera.loc[common_samples]
metabolites = metabolites.loc[common_samples]
metadata = metadata.loc[common_samples]

# Convert CD and UC into one IBD class
metadata["Benchmark.Label"] = metadata["Study.Group"].replace({
    "CD": "IBD",
    "UC": "IBD",
    "Control": "Control",
})

# Keep only IBD and Control
metadata = metadata[metadata["Benchmark.Label"].isin(["IBD", "Control"])]
genera = genera.loc[metadata.index]
metabolites = metabolites.loc[metadata.index]

# Optional: balance IBD and Control
if BALANCE_CLASSES:
    control_samples = metadata[metadata["Benchmark.Label"] == "Control"].index.tolist()
    ibd_samples = metadata[metadata["Benchmark.Label"] == "IBD"].index.tolist()

    n = min(len(control_samples), len(ibd_samples))

    selected_controls = random.sample(control_samples, n)
    selected_ibd = random.sample(ibd_samples, n)

    selected_samples = selected_controls + selected_ibd
    random.shuffle(selected_samples)

    metadata = metadata.loc[selected_samples]
    genera = genera.loc[selected_samples]
    metabolites = metabolites.loc[selected_samples]

# Keep only named metabolites
named_metabolite_cols = [
    col for col in metabolites.columns
    if not col.endswith(": NA")
]

def simplify_genus_name(full_taxonomy: str) -> str:
    """
    Converts a full GTDB taxonomy string into the genus name.
    Example:
    d__Bacteria;...;g__Phocaeicola -> Phocaeicola
    """
    if "g__" in full_taxonomy:
        return full_taxonomy.split("g__")[-1]
    return full_taxonomy

def format_top_genera(sample_id: str) -> str:
    top = genera.loc[sample_id].sort_values(ascending=False).head(N_TOP_GENERA)
    entries = []
    for taxon, value in top.items():
        genus = simplify_genus_name(taxon)
        entries.append(f"{genus}: {value:.5f}")
    return "; ".join(entries)

def format_top_metabolites(sample_id: str) -> str:
    top = metabolites.loc[sample_id, named_metabolite_cols].sort_values(ascending=False)

    entries = []
    seen_names = set()

    for metabolite, value in top.items():
        readable_name = metabolite.split(": ", 1)[-1]

        # Skip duplicate metabolite names
        if readable_name in seen_names:
            continue

        seen_names.add(readable_name)
        entries.append(f"{readable_name}: {value:.2f}")

        if len(entries) == N_TOP_METABOLITES:
            break

    return "; ".join(entries)

def clean_value(value):
    """
    Converts missing values to 'unknown' for cleaner prompts.
    """
    if pd.isna(value):
        return "unknown"
    return value

def build_prompt(sample_id: str) -> str:
    row = metadata.loc[sample_id]
    
    age = clean_value(row.get("Age", "unknown"))
    fecal_calprotectin = clean_value(row.get("Fecal.Calprotectin", "unknown"))
    antibiotic = clean_value(row.get("antibiotic", "unknown"))
    immunosuppressant = clean_value(row.get("immunosuppressant", "unknown"))
    mesalamine = clean_value(row.get("mesalamine", "unknown"))
    steroids = clean_value(row.get("steroids", "unknown"))

    top_genera = format_top_genera(sample_id)
    top_metabolites = format_top_metabolites(sample_id)

    prompt = f"""<question>
Based on the fecal microbiome and metabolome profile, is this sample from an inflammatory bowel disease patient or a control individual?
</question>

<options>
A. IBD
B. Control
</options>

<metadata>
Dataset: {DATASET}
Age: {age}
Fecal calprotectin: {fecal_calprotectin}
Antibiotic use: {antibiotic}
Immunosuppressant use: {immunosuppressant}
Mesalamine use: {mesalamine}
Steroid use: {steroids}
</metadata>

<microbiome>
Top genera by relative abundance: {top_genera}
</microbiome>

<metabolome>
Top named metabolites by abundance/intensity: {top_metabolites}
</metabolome>
"""
    return prompt

records = []

for sample_id in metadata.index:
    label = metadata.loc[sample_id, "Benchmark.Label"]
    answer = "A" if label == "IBD" else "B"

    record = {
        "sample_id": sample_id,
        "dataset": DATASET,
        "task": "IBD_vs_Control",
        "source_label": metadata.loc[sample_id, "Study.Group"],
        "benchmark_label": label,
        "answer": answer,
        "prompt": build_prompt(sample_id),
    }

    records.append(record)

out_path = out_dir / "franzosa_ibd_binary_prompts.jsonl"

with open(out_path, "w", encoding="utf-8") as f:
    for record in records:
        f.write(json.dumps(record) + "\n")

print(f"Saved {len(records)} prompts to {out_path}")
print(metadata["Benchmark.Label"].value_counts())