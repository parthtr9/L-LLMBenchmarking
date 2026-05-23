"""Run hosted Longevity-LLM against LongeBench tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from datasets import Dataset, load_dataset
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

LOGGER = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://sqrq2pj09htgequ0.us-east-2.aws.endpoints.huggingface.cloud"
DEFAULT_MODEL = "longevity-llm"
ANSWER_LETTER_RE = re.compile(r"(?<![A-Za-z])([A-F])(?![A-Za-z])")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
THINK_RE = re.compile(r"(?:<think>)?(.*?)</think>\s*", flags=re.DOTALL)


@dataclass(frozen=True)
class EvalConfig:
    """Runtime configuration for a LongeBench evaluation."""

    endpoint_url: str
    api_key: str
    model: str
    max_tokens: int
    temperature: float
    timeout: float
    think: bool
    seed: int


@dataclass(frozen=True)
class EvalRecord:
    """Single model response and parsed scoring fields."""

    row_index: int
    lb_id: str
    display_name: str | None
    metric: str | None
    format: str | None
    input_hash: str
    raw_response: str | None
    reasoning: str | None
    extracted_answer: str | float | None
    gold: str
    usage: dict[str, Any] | None
    latency_s: float | None
    error: str | None


def setup_logging() -> None:
    """Configure process logging."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def normalize_endpoint(endpoint_url: str) -> str:
    """Return an OpenAI SDK base URL ending in /v1."""

    endpoint_url = endpoint_url.rstrip("/")
    if endpoint_url.endswith("/v1"):
        return endpoint_url
    return f"{endpoint_url}/v1"


def load_eval_dataset(
    config_name: str,
    split: str,
    lb_id: str | None,
    cache_dir: Path,
    token: str | None,
) -> Dataset:
    """Load LongeBench and optionally filter to one task id."""

    dataset = load_dataset(
        "insilicomedicine/longebench",
        config_name,
        split=split,
        cache_dir=str(cache_dir),
        token=token,
    )
    if lb_id:
        dataset = dataset.filter(lambda row: row["lb_id"] == lb_id)
    return dataset


def select_rows(dataset: Dataset, limit: int | None) -> list[tuple[int, dict[str, Any]]]:
    """Materialize selected dataset rows while preserving original row indices."""

    selected = dataset if limit is None else dataset.select(range(min(limit, len(dataset))))
    return [(index, dict(row)) for index, row in enumerate(selected)]


def hash_messages(messages: list[dict[str, str]]) -> str:
    """Hash input messages for reproducible logging without duplicating prompt text."""

    payload = json.dumps(messages, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ensure_messages(value: Any) -> list[dict[str, str]]:
    """Return a normalized ChatML message list from a dataset field."""

    if isinstance(value, str):
        value = json.loads(value)
    return [dict(message) for message in value]


def split_reasoning(raw: str) -> tuple[str | None, str]:
    """Split Qwen think traces from final answer when present."""

    match = THINK_RE.search(raw)
    if match and "</think>" in raw:
        return match.group(1).strip(), raw[match.end() :].strip()
    return None, raw.strip()


def extract_number(text: str) -> float | None:
    """Extract the first numeric value from a model response."""

    match = NUMBER_RE.search(text)
    return float(match.group()) if match else None


def extract_answer(text: str, row: dict[str, Any]) -> str | float | None:
    """Extract a scoreable answer using LongeBench metadata hints."""

    clean = text.strip()
    metric = str(row.get("metric") or "").lower()
    output_format = str(row.get("format") or "").lower()

    if "mae" in metric or "regression" in output_format:
        return extract_number(clean)

    if "mcq" in output_format or "multiple" in output_format:
        letters = ANSWER_LETTER_RE.findall(clean)
        return letters[-1] if letters else clean

    return clean.strip().strip('"').strip("'")


def normalize_label(value: str) -> str:
    """Normalize a classification label for exact-match scoring."""

    return re.sub(r"\s+", " ", value.strip().strip('"').strip("'").lower())


def parse_set(value: str) -> set[str]:
    """Parse comma/newline separated set-generation answers."""

    return {
        item.strip().lower()
        for item in re.split(r"[,;\n]", value)
        if item.strip()
    }


def score_records(records: list[EvalRecord]) -> dict[str, Any]:
    """Compute quick aggregate metrics from completed records."""

    by_task: dict[str, list[EvalRecord]] = {}
    for record in records:
        by_task.setdefault(record.lb_id, []).append(record)

    summary: dict[str, Any] = {}
    for lb_id, task_records in by_task.items():
        valid = [record for record in task_records if record.error is None]
        metric = (valid[0].metric if valid else task_records[0].metric) or ""
        output_format = (valid[0].format if valid else task_records[0].format) or ""
        metric_key = metric.lower()
        format_key = output_format.lower()

        task_summary: dict[str, Any] = {
            "n": len(task_records),
            "completed": len(valid),
            "errors": len(task_records) - len(valid),
            "metric": metric,
            "format": output_format,
            "display_name": task_records[0].display_name,
        }

        if "mae" in metric_key or "regression" in format_key:
            pairs = []
            for record in valid:
                gold_number = extract_number(record.gold)
                if isinstance(record.extracted_answer, float) and gold_number is not None:
                    pairs.append((record.extracted_answer, gold_number))
            if pairs:
                errors = [abs(pred - gold) for pred, gold in pairs]
                task_summary["mae"] = statistics.fmean(errors)
        elif "jaccard" in metric_key or "set" in format_key:
            scores = []
            for record in valid:
                pred = parse_set(str(record.extracted_answer or ""))
                gold = parse_set(record.gold)
                if pred or gold:
                    scores.append(len(pred & gold) / len(pred | gold))
            if scores:
                task_summary["jaccard"] = statistics.fmean(scores)
        else:
            matches = [
                normalize_label(str(record.extracted_answer))
                == normalize_label(record.gold)
                for record in valid
                if record.extracted_answer is not None
            ]
            if matches:
                task_summary["accuracy"] = sum(matches) / len(matches)

        summary[lb_id] = task_summary

    return summary


def build_client(config: EvalConfig) -> OpenAI:
    """Build an OpenAI-compatible client for the hosted endpoint."""

    return OpenAI(
        base_url=normalize_endpoint(config.endpoint_url),
        api_key=config.api_key,
        timeout=config.timeout,
    )


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
def call_model(
    client: OpenAI,
    config: EvalConfig,
    messages: list[dict[str, str]],
) -> Any:
    """Call the hosted chat-completions endpoint with retry."""

    return client.chat.completions.create(
        model=config.model,
        messages=messages,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        seed=config.seed,
        extra_body={"chat_template_kwargs": {"enable_thinking": config.think}},
    )


def evaluate_row(
    client: OpenAI,
    config: EvalConfig,
    row_index: int,
    row: dict[str, Any],
    dry_run: bool,
) -> EvalRecord:
    """Evaluate one LongeBench row."""

    all_messages = ensure_messages(row["messages"])
    messages = all_messages[:-1]
    gold = str(all_messages[-1]["content"]).strip()
    started = time.perf_counter()

    if dry_run:
        return EvalRecord(
            row_index=row_index,
            lb_id=row["lb_id"],
            display_name=row.get("display_name"),
            metric=row.get("metric"),
            format=row.get("format"),
            input_hash=hash_messages(messages),
            raw_response=None,
            reasoning=None,
            extracted_answer=None,
            gold=gold,
            usage=None,
            latency_s=None,
            error=None,
        )

    try:
        response = call_model(client, config, messages)
        latency = time.perf_counter() - started
        message = response.choices[0].message
        raw = (message.content or "").strip()
        reasoning = getattr(message, "reasoning_content", None)
        answer = raw
        if not reasoning:
            reasoning, answer = split_reasoning(raw)
        usage = response.usage.model_dump() if response.usage else None
        return EvalRecord(
            row_index=row_index,
            lb_id=row["lb_id"],
            display_name=row.get("display_name"),
            metric=row.get("metric"),
            format=row.get("format"),
            input_hash=hash_messages(messages),
            raw_response=raw,
            reasoning=reasoning,
            extracted_answer=extract_answer(answer, row),
            gold=gold,
            usage=usage,
            latency_s=latency,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 - keep full eval runs alive.
        LOGGER.exception("row %s failed", row_index)
        return EvalRecord(
            row_index=row_index,
            lb_id=row["lb_id"],
            display_name=row.get("display_name"),
            metric=row.get("metric"),
            format=row.get("format"),
            input_hash=hash_messages(messages),
            raw_response=None,
            reasoning=None,
            extracted_answer=None,
            gold=gold,
            usage=None,
            latency_s=time.perf_counter() - started,
            error=str(exc),
        )


def write_jsonl(path: Path, records: list[EvalRecord]) -> None:
    """Write evaluation records as JSONL."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda item: item.row_index):
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    """Write aggregate metrics as JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    """Run the CLI workflow."""

    load_dotenv()
    endpoint = args.endpoint_url or os.getenv("HF_ENDPOINT_URL") or DEFAULT_ENDPOINT
    api_key = args.api_key or os.getenv("HF_TOKEN") or "EMPTY"
    model = args.model or os.getenv("LONGBENCH_MODEL") or DEFAULT_MODEL
    config = EvalConfig(
        endpoint_url=endpoint,
        api_key=api_key,
        model=model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        timeout=args.timeout,
        think=args.think,
        seed=args.seed,
    )

    lb_id = args.lb_id or None
    dataset = load_eval_dataset(
        args.dataset_config,
        args.split,
        lb_id,
        args.cache_dir,
        os.getenv("HF_TOKEN"),
    )
    rows = select_rows(dataset, args.limit)
    LOGGER.info("loaded %s rows from config=%s lb_id=%s", len(rows), args.dataset_config, lb_id)

    client = build_client(config)
    records: list[EvalRecord] = []

    if args.concurrency == 1 or args.dry_run:
        for row_index, row in rows:
            records.append(evaluate_row(client, config, row_index, row, args.dry_run))
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = [
                executor.submit(evaluate_row, client, config, row_index, row, False)
                for row_index, row in rows
            ]
            for future in as_completed(futures):
                records.append(future.result())
                if len(records) % 10 == 0:
                    LOGGER.info("completed %s/%s rows", len(records), len(rows))

    write_jsonl(args.output, records)
    summary = score_records(records)
    write_summary(args.summary_output, summary)
    LOGGER.info("wrote records to %s", args.output)
    LOGGER.info("wrote summary to %s", args.summary_output)
    LOGGER.info("summary: %s", json.dumps(summary, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-config", default="benchmark", choices=["benchmark", "extra"])
    parser.add_argument("--split", default="eval")
    parser.add_argument("--lb-id", default="LB-0038", help="Task id to run; pass '' for all tasks.")
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/huggingface"))
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to run.")
    parser.add_argument("--concurrency", type=int, default=4, help="Keep <= 8 for the shared endpoint.")
    parser.add_argument("--output", type=Path, default=Path("outputs/longebench_records.jsonl"))
    parser.add_argument("--summary-output", type=Path, default=Path("outputs/longebench_summary.json"))
    parser.add_argument("--endpoint-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-tokens", type=int, default=500)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Load rows and write hashes without API calls.")
    return parser


def main() -> None:
    """CLI entrypoint."""

    setup_logging()
    args = build_parser().parse_args()
    if args.concurrency > 8:
        raise SystemExit("Please keep --concurrency <= 8 for the shared endpoint.")
    run(args)


if __name__ == "__main__":
    main()
