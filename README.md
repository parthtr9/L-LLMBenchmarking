# L-LLMBenchmarking

Utilities for the Caltech Longevity Hackathon Track 01 work. The current
pipeline can run the hosted Longevity-LLM endpoint against the public
LongeBench benchmark dataset and save reproducible per-row outputs.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Put the HuggingFace endpoint token in `.env`:

```bash
HF_ENDPOINT_URL=https://sqrq2pj09htgequ0.us-east-2.aws.endpoints.huggingface.cloud
HF_TOKEN=hf_...
LONGBENCH_MODEL=longevity-llm
```

Do not commit `.env`.

## Smoke test LongeBench

The default command runs 20 rows of `LB-0038` from the benchmark split, drops
the gold assistant answer via `messages[:-1]`, calls `/v1/chat/completions`,
and writes both raw records and a quick metric summary.

```bash
.venv/bin/python -m src.eval.longebench_runner \
  --lb-id LB-0038 \
  --limit 20 \
  --concurrency 4 \
  --output outputs/lb0038_records.jsonl \
  --summary-output outputs/lb0038_summary.json
```

Useful variants:

```bash
# Verify dataset loading and output shape without calling the endpoint.
.venv/bin/python -m src.eval.longebench_runner --dry-run --limit 3

# Run the held-out extra split.
.venv/bin/python -m src.eval.longebench_runner --dataset-config extra --lb-id LB-0038

# Enable Qwen thinking mode. This is slower and should use more tokens.
.venv/bin/python -m src.eval.longebench_runner --think --max-tokens 3000
```

Keep `--concurrency` at 8 or below because the endpoint is shared.
