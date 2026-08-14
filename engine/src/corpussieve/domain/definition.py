from pathlib import Path

import yaml  # type: ignore[import-untyped]

from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.hashing import canonical_json_hash


def load_domain(path: Path | str) -> DomainDefinition:
    """Load and validate DomainDefinition from YAML file path."""
    p = Path(path).resolve()
    if not p.exists():
        raise CorpusSieveError(
            ErrorCode.INTERNAL_ERROR,
            f"Domain definition file '{p}' does not exist.",
        )

    try:
        content = p.read_text(encoding="utf-8")
        raw_data = yaml.safe_load(content)
        if not isinstance(raw_data, dict):
            raise CorpusSieveError(
                ErrorCode.INTERNAL_ERROR,
                f"Domain definition file '{p}' must contain a YAML mapping/dictionary.",
            )
        return DomainDefinition.model_validate(raw_data)
    except yaml.YAMLError as ye:
        mark = getattr(ye, "problem_mark", None)
        line_info = f" line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise CorpusSieveError(
            ErrorCode.INTERNAL_ERROR,
            f"YAML syntax error in domain file '{p}'{line_info}: {ye}",
        ) from ye
    except Exception as e:
        if isinstance(e, CorpusSieveError):
            raise
        raise CorpusSieveError(
            ErrorCode.INTERNAL_ERROR,
            f"Invalid domain definition in '{p}': {e}",
        ) from e


def save_domain(defn: DomainDefinition, path: Path | str) -> None:
    """Save DomainDefinition to YAML file with stable key ordering matching model field order."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = defn.model_dump(mode="json")
    yaml_str = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    p.write_text(yaml_str, encoding="utf-8")


def domain_hash(defn: DomainDefinition) -> str:
    """Compute sha256 hex digest of canonicalized JSON representation of DomainDefinition."""
    return canonical_json_hash(defn.model_dump(mode="json"))
