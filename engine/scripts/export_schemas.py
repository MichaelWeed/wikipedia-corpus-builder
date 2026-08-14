import json
from pathlib import Path
from typing import Any

from corpussieve.contracts.corpus import CorpusRecord
from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.events import ProgressEvent
from corpussieve.contracts.llm_io import BranchReviewResult
from corpussieve.contracts.lock import DomainLock
from corpussieve.contracts.manifest import ManifestRecord
from corpussieve.contracts.project import ProjectFile
from corpussieve.contracts.report import BuildReport

MODELS: list[tuple[str, Any]] = [
    ("domain-definition.schema.json", DomainDefinition),
    ("domain-lock.schema.json", DomainLock),
    ("manifest-record.schema.json", ManifestRecord),
    ("corpus-record.schema.json", CorpusRecord),
    ("project-file.schema.json", ProjectFile),
    ("build-report.schema.json", BuildReport),
    ("branch-review-result.schema.json", BranchReviewResult),
    ("progress-event.schema.json", ProgressEvent),
]


def export_all_schemas(schemas_dir: Path) -> None:
    schemas_dir.mkdir(parents=True, exist_ok=True)
    for filename, model in MODELS:
        schema_data = model.model_json_schema()
        json_text = json.dumps(schema_data, indent=2, sort_keys=True) + "\n"
        target_path = schemas_dir / filename
        target_path.write_text(json_text, encoding="utf-8")
        print(f"Exported {target_path}")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent.parent
    output_dir = repo_root / "schemas"
    export_all_schemas(output_dir)
