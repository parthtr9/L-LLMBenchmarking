#!/usr/bin/env python3
"""
normalize.py — Step 1 of the longevity benchmark pipeline.

Converts biological datasets (MAF, Borenstein-style TSV/CSV, or other tabular
formats) into two output files:

  1. dataset.jsonl — one record per sample:
     {
       "sample_id": "...",
       "dataset": "...",
       "modality": "...",
       "features": {"feature_name": value, ...},
       "label": <age as float>,   # hidden from LLM during testing
       "metadata": {...}
     }

  2. dataset_manifest.json — metadata blueprint + cleaned CSV preview:
     {
       "metadata": [
         {"column_code": "cholesterol", "description": "..."},
         ...
       ],
       "csv_preview": "col1,col2,...\nval,val,...\n..."
     }

Usage:
  python normalize.py <path_to_file_or_folder> [--out output.jsonl] [--metadata path]

Supported input layouts:
  1. MAF (MetaboLights) — metabolites as rows, samples as columns
  2. Borenstein-style — samples as rows, features as columns (+ optional metadata TSV/CSV)
  3. Generic wide/long tables — Claude infers the mapping
"""

import argparse
import csv
import io
import json
import os
import re
import sys

import anthropic

# ── Constants ──────────────────────────────────────────────────────────────────

ANTHROPIC_MODEL = "claude-sonnet-4-5"

# Columns that are never features in MAF files
MAF_ANNOTATION_COLS = {
    "database_identifier", "chemical_formula", "smiles", "inchi",
    "metabolite_identification", "mass_to_charge", "fragmentation",
    "modifications", "charge", "retention_time", "taxid", "species",
    "database", "database_version", "reliability", "uri",
    "search_engine", "search_engine_score",
    "smallmolecule_abundance_sub", "smallmolecule_abundance_stdev_sub",
    "smallmolecule_abundance_std_error_sub",
}

# ── Utilities ──────────────────────────────────────────────────────────────────

def sniff_delimiter(path: str) -> str:
    # Trust the file extension first — most reliable signal
    if path.lower().endswith(".tsv"):
        return "\t"
    if path.lower().endswith(".csv"):
        return ","

    # Fall back to sniffing, but exclude | since it appears in lipid nomenclature
    with open(path, "r", errors="replace") as fh:
        sample = fh.read(4096)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        return dialect.delimiter
    except csv.Error:
        return "\t" if "\t" in sample else ","


def read_table(path: str) -> tuple[list[str], list[dict]]:
    """Return (headers, rows) where each row is a dict."""
    delim = sniff_delimiter(path)
    with open(path, "r", errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter=delim)
        headers = reader.fieldnames or []
        rows = list(reader)
    return list(headers), rows


def safe_float(val) -> float | None:
    try:
        f = float(str(val).strip())
        return None if (f != f) else f  # NaN guard
    except (ValueError, TypeError):
        return None


def is_sample_col(name: str) -> bool:
    """Heuristic: MAF sample columns are short IDs without spaces."""
    return bool(
        name
        and len(name) <= 20
        and " " not in name
        and name.lower() not in MAF_ANNOTATION_COLS
        and not name.lower().startswith("unnamed")
    )


# ── Format detection ────────────────────────────────────────────────────────────

def detect_format(headers: list[str], rows: list[dict], path: str) -> str:
    """Return 'maf', 'borenstein', or 'generic'."""
    lower_heads = [h.lower() for h in headers]

    if "metabolite_identification" in lower_heads and "mass_to_charge" in lower_heads:
        return "maf"

    n_numeric_cols = 0
    for h in headers[1:]:
        vals = [safe_float(r.get(h, "")) for r in rows[:20]]
        if sum(v is not None for v in vals) > 10:
            n_numeric_cols += 1
    if n_numeric_cols > 5:
        return "borenstein"

    return "generic"


# ── Claude schema inference ─────────────────────────────────────────────────────

def infer_schema_with_claude(
    headers: list[str], sample_rows: list[dict], filename: str,
    client: anthropic.Anthropic
) -> dict:
    """
    Ask Claude to classify columns as: sample_id, label, metadata, feature, ignore.
    For very wide files (>500 cols) skips the API call — col 0 is sample_id, rest features.
    """
    if len(headers) > 500:
        schema = {h: "feature" for h in headers}
        schema[headers[0]] = "sample_id"

        # Scan the first 20 columns for obvious metadata/label patterns
        label_hints = {"age", "years", "survival", "lifespan", "ttd"}
        metadata_hints = {"sex", "gender", "bmi", "disease", "diabetes",
                        "diagnosis", "cohort", "group", "condition",
                        "individual", "subject", "participant", "ethnicity"}

        for h in headers[1:20]:
            hl = h.lower().strip()
            if any(hint in hl for hint in label_hints):
                schema[h] = "label"
            elif any(hint in hl for hint in metadata_hints):
                schema[h] = "metadata"

        print(
            f"  [schema] {len(headers)} columns — auto-assigned first 20 cols, "
            f"rest as features",
            file=sys.stderr,
        )
        return schema

    preview = {h: [r.get(h, "") for r in sample_rows[:5]] for h in headers[:40]}
    preview_text = json.dumps(preview, indent=2)

    prompt = f"""You are analysing a biological dataset file: "{filename}".
Here is a preview of the first 5 rows for up to 40 columns (column -> [val1..val5]):

{preview_text}

Classify each column into one of these roles:
- "sample_id": the unique identifier for each sample/patient
- "label": a biological or clinical outcome to PREDICT (age, survival time, disease status)
- "metadata": demographic or clinical covariates (sex, BMI, disease, cohort, etc.)
- "feature": a quantitative biological measurement (abundance, expression, etc.)
- "ignore": administrative columns, redundant IDs, or empty columns

Return ONLY a JSON object mapping column names to roles, like:
{{"SampleID": "sample_id", "Age": "label", "Sex": "metadata", "Cholesterol": "feature"}}

Rules:
- There must be exactly one sample_id.
- Label columns often contain numbers that look like ages (18-100) or survival times.
- Feature columns typically contain many numeric values close together.
- If unsure between label and metadata, prefer metadata.
"""

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def infer_modality(headers: list[str], filename: str) -> str:
    text = " ".join(headers + [filename]).lower()
    if any(k in text for k in ["hmdb", "metabolite", "lipid", "maf", "metabolom"]):
        return "metabolomics"
    if any(k in text for k in ["genus", "species", "otu", "asv", "microbi", "taxa"]):
        return "metagenomics"
    if any(k in text for k in ["ensg", "ensembl", "tpm", "fpkm", "gene", "transcript", "rna"]):
        return "transcriptomics"
    if any(k in text for k in ["protein", "olink", "npx", "proteom"]):
        return "proteomics"
    if any(k in text for k in ["clinical", "nhanes", "blood", "wbc", "hemoglobin", "creatinine"]):
        return "clinical"
    return "unknown"


# ── Parsers ─────────────────────────────────────────────────────────────────────

def parse_maf(headers: list[str], rows: list[dict], dataset_name: str) -> list[dict]:
    sample_cols = [h for h in headers if is_sample_col(h)]

    def feature_name(row: dict, seen: dict) -> str:
        name = row.get("metabolite_identification") or row.get("database_identifier")
        name = str(name).strip() if name else ""
        if not name or name.lower() == "nan":
            mz = row.get("mass_to_charge", "").strip()
            name = f"mz_{mz}" if mz else "feature_unknown"
        if name in seen:
            mz = row.get("mass_to_charge", "").strip()
            mod = row.get("modifications", "").strip()
            suffix = f"_{mz}" if mz else ""
            if mod:
                suffix += f"_{mod}"
            name = f"{name}{suffix}"
        seen[name] = True
        return name

    seen: dict = {}
    feature_names = [feature_name(row, seen) for row in rows]

    records = []
    for sample_col in sample_cols:
        features = {}
        for fname, row in zip(feature_names, rows):
            val = safe_float(row.get(sample_col, ""))
            if val is not None:
                features[fname] = val
        if not features:
            continue
        records.append({
            "sample_id": sample_col,
            "dataset": dataset_name,
            "modality": "metabolomics",
            "features": features,
            "label": None,
            "metadata": {},
        })

    return records


def parse_borenstein(
    headers: list[str], rows: list[dict], dataset_name: str,
    schema: dict, filename: str
) -> list[dict]:
    modality = infer_modality(headers, filename)
    records = []
    for i, row in enumerate(rows):
        sample_id = None
        features = {}
        label = None
        metadata = {}
        for col, role in schema.items():
            val = row.get(col, "")
            if role == "sample_id":
                sample_id = str(val).strip()
            elif role == "feature":
                fval = safe_float(val)
                if fval is not None:
                    features[col] = fval
            elif role == "label":
                label = safe_float(val) or (str(val).strip() if val else None)
            elif role == "metadata":
                if val not in ("", None):
                    metadata[col] = str(val).strip()
        if not sample_id:
            sample_id = str(row.get(headers[0], f"sample_{i}")).strip()
        records.append({
            "sample_id": sample_id,
            "dataset": dataset_name,
            "modality": modality,
            "features": features,
            "label": label,
            "metadata": metadata,
        })
    return records


def merge_metadata(
    records: list[dict], meta_path: str, client: anthropic.Anthropic
) -> list[dict]:
    meta_headers, meta_rows = read_table(meta_path)
    if not meta_rows:
        return records
    schema = infer_schema_with_claude(
        meta_headers, meta_rows[:20], os.path.basename(meta_path), client
    )
    id_col = next((c for c, r in schema.items() if r == "sample_id"), meta_headers[0])
    meta_index = {str(row.get(id_col, "")).strip(): row for row in meta_rows}
    label_col = next((c for c, r in schema.items() if r == "label"), None)
    metadata_cols = [c for c, r in schema.items() if r == "metadata"]
    for rec in records:
        meta_row = meta_index.get(rec["sample_id"], {})
        if meta_row:
            if label_col and rec["label"] is None:
                lval = meta_row.get(label_col, "")
                rec["label"] = safe_float(lval) or (str(lval).strip() if lval else None)
            for col in metadata_cols:
                val = meta_row.get(col, "")
                if val not in ("", None):
                    rec["metadata"][col] = str(val).strip()
    return records


# ── Age validation ─────────────────────────────────────────────────────────────

def validate_age(records: list[dict]) -> None:
    """Hard stop if any record is missing a valid numeric age label."""
    total = len(records)
    if total == 0:
        print("\n[validate] FAILED: No records were produced.", file=sys.stderr)
        sys.exit(1)

    missing_label = [r for r in records if r["label"] is None]
    non_numeric   = [r for r in records if r["label"] is not None
                     and not isinstance(r["label"], (int, float))]
    out_of_range  = [r for r in records if isinstance(r["label"], (int, float))
                     and not (0 <= r["label"] <= 130)]

    errors = []
    if missing_label:
        errors.append(
            f"  * {len(missing_label)}/{total} records have no age (label is null).\n"
            f"    Sample IDs: {[r['sample_id'] for r in missing_label[:5]]}"
            + (" ..." if len(missing_label) > 5 else "")
        )
    if non_numeric:
        errors.append(
            f"  * {len(non_numeric)}/{total} records have a non-numeric label.\n"
            f"    Values seen: {[r['label'] for r in non_numeric[:5]]}"
        )
    if out_of_range:
        errors.append(
            f"  * {len(out_of_range)}/{total} records have an age outside 0-130.\n"
            f"    Values seen: {[r['label'] for r in out_of_range[:5]]}"
        )

    if errors:
        print("\n[validate] FAILED -- age column is missing or invalid:\n", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        print(
            "\nFix options:\n"
            "  1. Supply a metadata file:  python normalize.py data.tsv --metadata metadata.tsv\n"
            "  2. If running on a folder, add a metadata.tsv to that folder.\n"
            "  3. Check that Claude inferred your age column as 'label', not 'metadata'.",
            file=sys.stderr,
        )
        sys.exit(1)

    ages = [r["label"] for r in records]
    print(f"  Age range: {min(ages):.1f} - {max(ages):.1f} (mean {sum(ages)/len(ages):.1f})")


# ── Manifest generation ────────────────────────────────────────────────────────

def generate_manifest(records: list[dict], client: anthropic.Anthropic) -> dict:
    """
    Produces dataset_manifest.json with two sections:

      "metadata": list of {column_code, description} — one entry per feature/label/metadata
                  column, with Claude-generated plain-English descriptions.

      "csv_preview": a clean CSV string of the normalized data (all columns, up to 10 rows),
                     with the label column included so downstream steps can see the age range.

    This file is what step 2 (topic_extractor.py) reads to identify biology topics.
    """
    if not records:
        return {"metadata": [], "csv_preview": ""}

    print("[manifest] Generating column descriptions with Claude...", file=sys.stderr)

    # ── Collect all unique column names across the dataset ──
    all_feature_cols = set()
    all_metadata_cols = set()
    for r in records:
        all_feature_cols.update(r["features"].keys())
        all_metadata_cols.update(r["metadata"].keys())

    feature_cols = sorted(all_feature_cols)
    metadata_cols = sorted(all_metadata_cols)
    modality = records[0].get("modality", "unknown")

    # ── Sample values for the description prompt (cap at 50 features to stay concise) ──
    sample_records = records[:10]
    preview_features = feature_cols[:50]

    col_samples: dict[str, list] = {}
    for col in preview_features:
        col_samples[col] = [r["features"].get(col) for r in sample_records]
    for col in metadata_cols:
        col_samples[col] = [r["metadata"].get(col) for r in sample_records]
    col_samples["age"] = [r["label"] for r in sample_records]

    prompt = f"""You are documenting a biological dataset for a longevity research benchmark.
Dataset modality: {modality}
Total columns: {len(feature_cols)} features + {len(metadata_cols)} metadata columns + 1 age label

Below is a sample of column names and their values across 10 samples:
{json.dumps(col_samples, indent=2)}

For EACH column listed above, write a single concise sentence describing:
- What the measurement represents biologically
- Its data type (numerical continuous, numerical count, categorical binary, categorical ordinal, etc.)
- Units if inferrable from the column name

Return ONLY a JSON array, one object per column, in this exact format:
[
  {{"column_code": "exact_column_name", "description": "One sentence description."}},
  ...
]

Include every column: all features, all metadata columns, and the "age" column.
Do not add any text outside the JSON array.
"""

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    described_cols: list[dict] = json.loads(raw)

    # ── If there are more feature columns than Claude described, stub the rest ──
    described_names = {d["column_code"] for d in described_cols}
    for col in feature_cols:
        if col not in described_names:
            described_cols.append({
                "column_code": col,
                "description": f"{modality.capitalize()} measurement (numerical continuous variable).",
            })

    # ── Build the CSV preview ──
    # Columns: sample_id, age, all metadata cols, all feature cols (capped at 200)
    csv_feature_cols = feature_cols[:200]
    csv_columns = ["sample_id", "age"] + metadata_cols + csv_feature_cols
    csv_rows = []
    for r in records[:10]:
        row = {"sample_id": r["sample_id"], "age": r["label"]}
        row.update(r["metadata"])
        for col in csv_feature_cols:
            row[col] = r["features"].get(col, "")
        csv_rows.append(row)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=csv_columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(csv_rows)
    csv_preview = buf.getvalue()

    return {
        "metadata": described_cols,
        "csv_preview": csv_preview,
    }


# ── Normalizers ────────────────────────────────────────────────────────────────

def normalize_file(
    path: str, client: anthropic.Anthropic, meta_path: str | None = None
) -> list[dict]:
    dataset_name = os.path.splitext(os.path.basename(path))[0]
    print(f"[normalize] Reading: {path}", file=sys.stderr)

    headers, rows = read_table(path)
    if not rows:
        print(f"[normalize] WARNING: empty file {path}", file=sys.stderr)
        return []

    fmt = detect_format(headers, rows, path)
    print(f"[normalize] Detected format: {fmt} ({len(rows)} rows, {len(headers)} cols)",
          file=sys.stderr)

    records: list[dict] = []

    if fmt == "maf":
        records = parse_maf(headers, rows, dataset_name)
    elif fmt in ("borenstein", "generic"):
        print("[normalize] Inferring schema with Claude...", file=sys.stderr)
        schema = infer_schema_with_claude(headers, rows[:20],
                                          os.path.basename(path), client)
        records = parse_borenstein(headers, rows, dataset_name, schema, path)

    if meta_path and os.path.isfile(meta_path):
        print(f"[normalize] Merging metadata from: {meta_path}", file=sys.stderr)
        records = merge_metadata(records, meta_path, client)

    print(f"[normalize] Produced {len(records)} sample records.", file=sys.stderr)
    return records


def normalize_directory(folder: str, client: anthropic.Anthropic) -> list[dict]:
    all_records: list[dict] = []
    files = os.listdir(folder)

    meta_file = None
    for f in files:
        if "meta" in f.lower() and f.endswith((".tsv", ".csv")):
            meta_file = os.path.join(folder, f)
            break

    for f in sorted(files):
        if f.startswith(".") or f.endswith((".RData", ".R", ".py", ".md")):
            continue
        if f.endswith((".tsv", ".csv", ".txt")):
            fpath = os.path.join(folder, f)
            if fpath == meta_file:
                continue
            records = normalize_file(fpath, client, meta_path=meta_file)
            all_records.extend(records)

    return all_records


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Normalize biological datasets to JSONL + manifest")
    parser.add_argument("input", help="Path to a file or directory")
    parser.add_argument("--out", default="dataset.jsonl",
                        help="Output JSONL path (default: dataset.jsonl)")
    parser.add_argument("--metadata", default=None,
                        help="Path to external metadata file (for single-file inputs)")
    parser.add_argument("--skip-age-check", action="store_true",
                        help="Bypass the age validation gate (not recommended)")
    args = parser.parse_args()

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    # ── Step 1: Normalize ──
    if os.path.isdir(args.input):
        records = normalize_directory(args.input, client)
    else:
        records = normalize_file(args.input, client, meta_path=args.metadata)

    # ── Step 2: Validate age ──
    print("\n[validate] Checking age column...")
    if args.skip_age_check:
        print("  WARNING: age check skipped via --skip-age-check", file=sys.stderr)
    else:
        validate_age(records)

    # ── Step 3: Write dataset.jsonl ──
    with open(args.out, "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    print(f"\n✓ Wrote {len(records)} records → {args.out}")

    # ── Step 4: Generate and write manifest ──
    manifest_path = args.out.replace(".jsonl", "_manifest.json")
    manifest = generate_manifest(records, client)
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"✓ Wrote manifest ({len(manifest['metadata'])} column descriptions) → {manifest_path}")


if __name__ == "__main__":
    main()