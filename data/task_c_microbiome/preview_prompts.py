import json
from pathlib import Path

path = Path("benchmark_prompts/franzosa_ibd_binary_prompts.jsonl")

with open(path, "r", encoding="utf-8") as f:
    records = [json.loads(line) for line in f]

print(f"Loaded {len(records)} prompts")

for i, record in enumerate(records[:3], start=1):
    print("\n" + "=" * 100)
    print(f"PROMPT {i}")
    print("=" * 100)
    print(f"Sample ID: {record['sample_id']}")
    print(f"Source label: {record['source_label']}")
    print(f"Benchmark label: {record['benchmark_label']}")
    print(f"Answer: {record['answer']}")
    print("\nPrompt:")
    print(record["prompt"])