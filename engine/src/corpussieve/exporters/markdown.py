import json
import os
import shutil
from pathlib import Path
from typing import Any

import zstandard as zstd

from corpussieve.contracts.corpus import CorpusRecord
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.exporters.attribution import format_yaml_frontmatter, write_attribution
from corpussieve.exporters.naming import slugify
from corpussieve.normalization.wikitext_md import WikitextMarkdownNormalizer


def export_markdown(
    corpus_dir: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    """Export canonical corpus to RAG-ready Markdown directory."""
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

    staging_dir = out_dir.parent / f".staging-md-{os.getpid()}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    normalizer = WikitextMarkdownNormalizer()
    index_map: dict[str, str] = {}
    normalization_errors = 0

    for rec in records:
        doc = normalizer.normalize(rec)
        if doc.warnings:
            normalization_errors += len(doc.warnings)

        slug = slugify(rec.source.title)
        filename = f"{rec.source.page_id}-{slug}.md"
        file_path = staging_dir / filename

        frontmatter_str = format_yaml_frontmatter(doc.frontmatter)
        file_content = f"{frontmatter_str}\n{doc.markdown}\n"
        file_path.write_text(file_content, encoding="utf-8")

        if rec.document_id:
            index_map[rec.document_id] = filename

    (staging_dir / "_index.json").write_text(json.dumps(index_map, indent=2), encoding="utf-8")

    write_attribution(records, staging_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    os.replace(staging_dir, out_dir)

    return {
        "status": "PASSED",
        "exported_count": len(records),
        "normalization_errors": normalization_errors,
        "output_dir": str(out_dir),
    }
