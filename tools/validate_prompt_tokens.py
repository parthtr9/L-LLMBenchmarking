#!/usr/bin/env python3
"""Validate benchmark prompt lengths with the cl100k_base tokenizer.

Checks ChatML-style benchmark records in JSON, JSONL, or parquet files. The
ground-truth assistant answer is excluded from the prompt token count.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import tiktoken

DEFAULT_LIMIT = 30_000
ENCODING_NAME = "cl100k_base"


def load_records(path: Path) -> list[dict[str, Any]]:
    """Load records from JSONL, JSON list/object, or parquet."""
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        records = []
        with path.open(encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
                if not isinstance(record, dict):
                    raise ValueError(f"line {line_no}: record must be an object")
                records.append(record)
        return records

    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and isinstance(data.get("records"), list):
            records = data["records"]
        else:
            raise ValueError("JSON file must contain a list or an object with records[]")
        if not all(isinstance(record, dict) for record in records):
            raise ValueError("all JSON records must be objects")
        return records

    if suffix == ".parquet":
        return pd.read_parquet(path).to_dict("records")

    raise ValueError(f"unsupported file type: {path.suffix}")


def normalize_messages(value: Any) -> list[dict[str, Any]]:
    """Return messages as a list of ChatML message dicts."""
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        raise ValueError("messages must be a list or JSON string")
    if not value:
        raise ValueError("messages must not be empty")
    for i, message in enumerate(value):
        if not isinstance(message, dict):
            raise ValueError(f"messages[{i}] must be an object")
        if "role" not in message:
            raise ValueError(f"messages[{i}] missing role")
        if "content" not in message:
            raise ValueError(f"messages[{i}] missing content")
    return value


def prompt_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exclude the final assistant answer when it is the benchmark target."""
    if messages and messages[-1].get("role") == "assistant":
        return messages[:-1]
    return messages


def prompt_text(messages: list[dict[str, Any]]) -> str:
    """Serialize messages in a stable ChatML-like form for token counting."""
    parts = []
    for message in prompt_messages(messages):
        role = str(message.get("role", ""))
        content = message.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False, sort_keys=True)
        parts.append(f"<{role}>\n{content}")
    return "\n".join(parts)


def count_tokens(messages: list[dict[str, Any]], encoding: tiktoken.Encoding) -> int:
    return len(encoding.encode(prompt_text(messages)))


def record_id(record: dict[str, Any], fallback: int) -> Any:
    return record.get("lb_id") or record.get("id") or fallback


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that benchmark prompts stay under the token limit.",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="JSONL, JSON, or parquet task files")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum allowed tokens")
    parser.add_argument("--top", type=int, default=10, help="Number of longest prompts to print")
    args = parser.parse_args()

    encoding = tiktoken.get_encoding(ENCODING_NAME)
    failures: list[tuple[str, Any, str, str]] = []
    longest: list[tuple[int, str, Any, Any]] = []
    checked = 0

    for path in args.paths:
        try:
            records = load_records(path)
        except Exception as exc:
            failures.append((str(path), "-", "load_error", str(exc)))
            continue

        for i, record in enumerate(records):
            row_id = record_id(record, i)
            try:
                messages = normalize_messages(record["messages"])
                n_tokens = count_tokens(messages, encoding)
            except KeyError:
                failures.append((str(path), row_id, "malformed", "missing messages"))
                continue
            except Exception as exc:
                failures.append((str(path), row_id, "malformed", str(exc)))
                continue

            checked += 1
            longest.append((n_tokens, str(path), row_id, record.get("format")))
            if n_tokens > args.limit:
                failures.append((str(path), row_id, "over_limit", f"{n_tokens} > {args.limit}"))

    longest.sort(key=lambda item: item[0], reverse=True)

    print(f"checked: {checked}")
    print(f"encoding: {ENCODING_NAME}")
    print(f"limit: {args.limit}")
    print(f"max_tokens: {longest[0][0] if longest else 0}")
    print("\nlongest prompts:")
    for n_tokens, path, row_id, fmt in longest[: args.top]:
        print(f"  {n_tokens:6d}  {path}  {row_id}  {fmt}")

    if failures:
        print("\nfailures:")
        for path, row_id, kind, detail in failures[:50]:
            print(f"  {path}  {row_id}  {kind}  {detail}")
        if len(failures) > 50:
            print(f"  ... {len(failures) - 50} more failures")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
