import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from corpussieve.contracts.corpus import CorpusRecord


def write_attribution(records: list[CorpusRecord], output_dir: Path) -> None:
    """Write human-readable ATTRIBUTION.md and machine-readable attribution.json."""
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    project = records[0].source.project if records else "wikimedia"
    doc_entries = []

    for r in records:
        doc_entries.append(
            {
                "document_id": r.document_id,
                "title": r.source.title,
                "page_id": r.source.page_id,
                "revision_id": r.source.revision_id,
                "source_url": r.source.source_url,
                "license": "CC BY-SA 4.0",
            }
        )

    json_data = {
        "source_project": project,
        "license": "CC BY-SA 4.0 / GFDL",
        "total_documents": len(records),
        "documents": doc_entries,
    }
    (out_dir / "attribution.json").write_text(json.dumps(json_data, indent=2), encoding="utf-8")

    md_content = (
        f"# Corpus Attribution Statement\n\n"
        f"This dataset contains content extracted from **Wikipedia ({project})**.\n\n"
        "- **License**: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)\n"
        "  and GNU Free Documentation License (GFDL).\n"
        "- **Source**: Wikimedia Foundation dumps.\n"
        f"- **Total Documents**: {len(records):,}\n\n"
        "## Disclaimer & Responsibility\n"
        "CorpusSieve is an independent open-source tool and is not affiliated with, sponsored, "
        "or endorsed by the Wikimedia Foundation. Users are solely responsible for ensuring "
        "compliance with copyright and licensing terms for downstream model training.\n"
    )
    (out_dir / "ATTRIBUTION.md").write_text(md_content, encoding="utf-8")


def format_yaml_frontmatter(data: dict[str, Any]) -> str:
    """Format dictionary into YAML frontmatter string."""
    yaml_str = yaml.dump(data, sort_keys=False).strip()
    return f"---\n{yaml_str}\n---\n"
