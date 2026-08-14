import json
import os
import shutil
from pathlib import Path
from typing import Any

import zstandard as zstd

from corpussieve.contracts.corpus import CorpusContent, CorpusRecord
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.exporters.attribution import write_attribution
from corpussieve.normalization.wikitext_md import WikitextMarkdownNormalizer


def export_jsonl(
    corpus_dir: Path | str,
    output_dir: Path | str,
    normalized: bool = False,
) -> dict[str, Any]:
    """Export canonical corpus to plain uncompressed .jsonl file."""
    c_dir = Path(corpus_dir).resolve()
    out_dir = Path(output_dir).resolve()

    c_file = c_dir / "corpus.jsonl.zst"
    if not c_file.exists() and (c_dir / "corpus" / "corpus.jsonl.zst").exists():
        c_file = c_dir / "corpus" / "corpus.jsonl.zst"

    if not c_file.exists():
        raise CorpusSieveError(
            ErrorCode.INTERNAL_ERROR,
            f"Canonical corpus file '{c_file}' does not exist.",
        )

    # Read corpus records
    dctx = zstd.ZstdDecompressor()
    records: list[CorpusRecord] = []
    with c_file.open("rb") as f_in, dctx.stream_reader(f_in) as reader:
        text = reader.read().decode("utf-8")
        for line in text.splitlines():
            if line.strip():
                data = json.loads(line)
                records.append(CorpusRecord.model_validate(data))

    staging_dir = out_dir.parent / f".staging-jsonl-{os.getpid()}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    jsonl_filename = "corpus.normalized.jsonl" if normalized else "corpus.jsonl"
    jsonl_path = staging_dir / jsonl_filename

    normalizer = WikitextMarkdownNormalizer() if normalized else None
    exported_records: list[dict[str, Any]] = []

    with jsonl_path.open("w", encoding="utf-8") as f_out:
        for rec in records:
            if normalizer:
                doc = normalizer.normalize(rec)
                norm_rec = CorpusRecord(
                    document_id=rec.document_id,
                    source=rec.source,
                    categories=rec.categories,
                    selection=rec.selection,
                    content=CorpusContent(format="markdown", raw=doc.markdown),
                )
                line_data = norm_rec.model_dump(mode="json")
            else:
                line_data = rec.model_dump(mode="json")

            f_out.write(json.dumps(line_data, sort_keys=True) + "\n")
            exported_records.append(line_data)

    write_attribution(records, staging_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    os.replace(staging_dir, out_dir)

    return {
        "status": "PASSED",
        "exported_count": len(records),
        "jsonl_file": str(out_dir / jsonl_filename),
        "output_dir": str(out_dir),
    }
