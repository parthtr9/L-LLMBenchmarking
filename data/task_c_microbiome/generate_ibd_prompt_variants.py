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

metadata["Benchmark.Label"] = metadata["Study.Group"].replace({
    "CD": "IBD",
    "UC": "IBD",
    "Control": "Control",
})

metadata = metadata[metadata["Benchmark.Label"].isin(["IBD", "Control"])]
genera = genera.loc[metadata.index]
metabolites = metabolites.loc[metadata.index]

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

named_metabolite_cols = [
    col for col in metabolites.columns
    if not col.endswith(": NA")
]


def clean_value(value):
    if pd.isna(value):
        return "unknown"
    return value


def simplify_genus_name(full_taxonomy: str) -> str:
    if "g__" in full_taxonomy:
        return full_taxonomy.split("g__")[-1]
    return full_taxonomy


def format_top_genera(sample_id: str) -> str:
    top = genera.loc[sample_id].sort_values(ascending=False).head(N_TOP_GENERA)

    entries = []
    seen_names = set()

    for taxon, value in top.items():
        genus = simplify_genus_name(taxon)

        if genus in seen_names:
            continue

        seen_names.add(genus)
        entries.append(f"{genus}: {value:.5f}")

        if len(entries) == N_TOP_GENERA:
            break

    return "; ".join(entries)


def format_top_metabolites(sample_id: str) -> str:
    top = metabolites.loc[sample_id, named_metabolite_cols].sort_values(ascending=False)

    entries = []
    seen_names = set()

    for metabolite, value in top.items():
        readable_name = metabolite.split(": ", 1)[-1]

        if readable_name in seen_names:
            continue

        seen_names.add(readable_name)
        entries.append(f"{readable_name}: {value:.2f}")

        if len(entries) == N_TOP_METABOLITES:
            break

    return "; ".join(entries)


def get_metadata_block(sample_id: str) -> str:
    row = metadata.loc[sample_id]

    age = clean_value(row.get("Age", "unknown"))
    fecal_calprotectin = clean_value(row.get("Fecal.Calprotectin", "unknown"))
    antibiotic = clean_value(row.get("antibiotic", "unknown"))
    immunosuppressant = clean_value(row.get("immunosuppressant", "unknown"))
    mesalamine = clean_value(row.get("mesalamine", "unknown"))
    steroids = clean_value(row.get("steroids", "unknown"))

    return f"""<metadata>
Dataset: {DATASET}
Age: {age}
Fecal calprotectin: {fecal_calprotectin}
Antibiotic use: {antibiotic}
Immunosuppressant use: {immunosuppressant}
Mesalamine use: {mesalamine}
Steroid use: {steroids}
</metadata>"""


def get_microbiome_block(sample_id: str) -> str:
    top_genera = format_top_genera(sample_id)

    return f"""<microbiome>
Top genera by relative abundance: {top_genera}
</microbiome>"""


def get_metabolome_block(sample_id: str) -> str:
    top_metabolites = format_top_metabolites(sample_id)

    return f"""<metabolome>
Top named metabolites by abundance/intensity: {top_metabolites}
</metabolome>"""


def build_prompt(sample_id: str, variant: str) -> str:
    question = """<question>
Based on the provided fecal sample information, is this sample from an inflammatory bowel disease patient or a control individual?
</question>

<options>
A. IBD
B. Control
</options>"""

    metadata_block = get_metadata_block(sample_id)
    microbiome_block = get_microbiome_block(sample_id)
    metabolome_block = get_metabolome_block(sample_id)

    if variant == "metadata_only":
        context = metadata_block

    elif variant == "microbiome_only":
        context = microbiome_block

    elif variant == "metabolome_only":
        context = metabolome_block

    elif variant == "combined_omics":
        context = f"""{microbiome_block}

{metabolome_block}"""

    elif variant == "full_context":
        context = f"""{metadata_block}

{microbiome_block}

{metabolome_block}"""

    else:
        raise ValueError(f"Unknown prompt variant: {variant}")

    return f"""{question}

{context}
"""


def make_records(variant: str):
    records = []

    for sample_id in metadata.index:
        label = metadata.loc[sample_id, "Benchmark.Label"]
        answer = "A" if label == "IBD" else "B"

        record = {
            "sample_id": sample_id,
            "dataset": DATASET,
            "task": "IBD_vs_Control",
            "variant": variant,
            "source_label": metadata.loc[sample_id, "Study.Group"],
            "benchmark_label": label,
            "answer": answer,
            "prompt": build_prompt(sample_id, variant),
        }

        records.append(record)

    return records


def save_jsonl(records, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


variants = [
    "metadata_only",
    "microbiome_only",
    "metabolome_only",
    "combined_omics",
    "full_context",
]

print("\nGenerating prompt variants")
print("=" * 80)
print(f"Dataset: {DATASET}")
print(f"Samples: {len(metadata)}")
print("\nClass balance:")
print(metadata["Benchmark.Label"].value_counts())

manifest = []

for variant in variants:
    records = make_records(variant)
    out_path = out_dir / f"franzosa_ibd_{variant}.jsonl"
    save_jsonl(records, out_path)

    manifest.append({
        "variant": variant,
        "path": str(out_path),
        "n_prompts": len(records),
        "n_ibd": sum(r["benchmark_label"] == "IBD" for r in records),
        "n_control": sum(r["benchmark_label"] == "Control" for r in records),
    })

    print(f"Saved {len(records):3d} prompts: {out_path}")

manifest_path = out_dir / "franzosa_ibd_prompt_manifest.json"

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"\nSaved manifest: {manifest_path}")

print("\nDone.")