import json
from pathlib import Path
from collections import Counter

prompt_dir = Path("benchmark_prompts")

files = [
    "franzosa_ibd_metadata_only.jsonl",
    "franzosa_ibd_microbiome_only.jsonl",
    "franzosa_ibd_metabolome_only.jsonl",
    "franzosa_ibd_combined_omics.jsonl",
    "franzosa_ibd_full_context.jsonl",
]

print("\nValidating prompt variants")
print("=" * 100)

all_sample_sets = {}

for filename in files:
    path = prompt_dir / filename

    with open(path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]

    labels = Counter(record["benchmark_label"] for record in records)
    answers = Counter(record["answer"] for record in records)
    sample_ids = [record["sample_id"] for record in records]
    variants = Counter(record["variant"] for record in records)

    all_sample_sets[filename] = set(sample_ids)

    print(f"\nFile: {filename}")
    print("-" * 100)
    print(f"Records: {len(records)}")
    print(f"Labels: {dict(labels)}")
    print(f"Answers: {dict(answers)}")
    print(f"Variants: {dict(variants)}")
    print(f"Unique sample IDs: {len(set(sample_ids))}")

    first = records[0]

    print("\nFirst record metadata:")
    print(f"Sample ID: {first['sample_id']}")
    print(f"Source label: {first['source_label']}")
    print(f"Benchmark label: {first['benchmark_label']}")
    print(f"Answer: {first['answer']}")

    print("\nPrompt preview:")
    print(first["prompt"][:1200])

# Check that all files contain the same samples
reference_file = files[0]
reference_samples = all_sample_sets[reference_file]

print("\nCross-file sample consistency")
print("=" * 100)

for filename, sample_set in all_sample_sets.items():
    same_samples = sample_set == reference_samples
    print(f"{filename}: same samples as {reference_file}? {same_samples}")

print("\nDone.")