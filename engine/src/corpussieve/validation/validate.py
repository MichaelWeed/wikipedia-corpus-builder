import hashlib
import json
import random
from pathlib import Path
from typing import Any, Literal

import zstandard as zstd
from pydantic import BaseModel, ConfigDict

from corpussieve.contracts.lock import DomainLock


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["PASSED", "FAILED"]
    total_records: int
    spot_checked: int
    errors: list[str]


def validate_corpus(corpus_dir: Path | str, lock: DomainLock) -> ValidationResult:
    """Validate promoted canonical corpus files (corpus.jsonl.zst and manifest.jsonl.zst)."""
    c_dir = Path(corpus_dir).resolve()
    corpus_file = c_dir / "corpus.jsonl.zst"
    manifest_file = c_dir / "manifest.jsonl.zst"

    errors: list[str] = []

    if not corpus_file.exists():
        return ValidationResult(
            status="FAILED",
            total_records=0,
            spot_checked=0,
            errors=[f"Corpus file '{corpus_file}' does not exist."],
        )
    if not manifest_file.exists():
        return ValidationResult(
            status="FAILED",
            total_records=0,
            spot_checked=0,
            errors=[f"Manifest file '{manifest_file}' does not exist."],
        )

    # 1. Read manifest records
    manifest_records: list[dict[str, Any]] = []
    dctx = zstd.ZstdDecompressor()
    try:
        with manifest_file.open("rb") as f_man, dctx.stream_reader(f_man) as reader:
            text = reader.read().decode("utf-8")
            for line in text.splitlines():
                if line.strip():
                    manifest_records.append(json.loads(line))
    except Exception as e:
        errors.append(f"Failed reading manifest.jsonl.zst: {e}")

    # 2. Read corpus records
    corpus_records: list[dict[str, Any]] = []
    try:
        with corpus_file.open("rb") as f_corp, dctx.stream_reader(f_corp) as reader:
            text = reader.read().decode("utf-8")
            for line in text.splitlines():
                if line.strip():
                    corpus_records.append(json.loads(line))
    except Exception as e:
        errors.append(f"Failed reading corpus.jsonl.zst: {e}")

    if errors:
        return ValidationResult(
            status="FAILED",
            total_records=0,
            spot_checked=0,
            errors=errors,
        )

    # 3. Check counts match
    if len(corpus_records) != len(manifest_records):
        msg = f"Count mismatch: manifest={len(manifest_records)}, corpus={len(corpus_records)}"
        errors.append(msg)

    # 4. Check document IDs match
    man_docs = {r.get("document_id") for r in manifest_records if r.get("document_id")}
    corp_docs = {r.get("document_id") for r in corpus_records if r.get("document_id")}

    if man_docs != corp_docs:
        errors.append("Document ID set mismatch between manifest and corpus")

    # 5. Spot check N=25 random records against manifest content_hash
    seed_val = int(lock.lock_hash[:8], 16)
    rng = random.Random(seed_val)
    spot_sample = rng.sample(corpus_records, min(25, len(corpus_records)))
    man_hash_map = {
        r["document_id"]: r["content_hash"]
        for r in manifest_records
        if r.get("document_id") and r.get("content_hash")
    }

    for rec in spot_sample:
        doc_id = rec.get("document_id", "")
        raw_text = rec.get("content", {}).get("raw", "")
        calc_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        exp_hash = man_hash_map.get(doc_id)

        if calc_hash != exp_hash:
            msg = f"Content hash mismatch for '{doc_id}': calc {calc_hash}, exp {exp_hash}"
            errors.append(msg)

    status: Literal["PASSED", "FAILED"] = "PASSED" if not errors else "FAILED"
    return ValidationResult(
        status=status,
        total_records=len(corpus_records),
        spot_checked=len(spot_sample),
        errors=errors,
    )
