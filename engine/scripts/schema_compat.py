import json
import sys
from pathlib import Path


def check_schema_compatibility(old_dir: Path, new_dir: Path) -> list[str]:
    errors: list[str] = []
    for new_file in new_dir.glob("*.schema.json"):
        old_file = old_dir / new_file.name
        if not old_file.exists():
            continue

        try:
            old_schema = json.loads(old_file.read_text(encoding="utf-8"))
            new_schema = json.loads(new_file.read_text(encoding="utf-8"))

            old_required = set(old_schema.get("required", []))
            new_required = set(new_schema.get("required", []))

            removed = old_required - new_required
            if removed:
                errors.append(
                    f"{new_file.name}: Previously required fields removed: {sorted(removed)}"
                )
        except Exception as e:
            errors.append(f"Error checking {new_file.name}: {e}")

    return errors


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python schema_compat.py <old_schemas_dir> <new_schemas_dir>")
        sys.exit(1)

    old_path = Path(sys.argv[1])
    new_path = Path(sys.argv[2])

    compat_errors = check_schema_compatibility(old_path, new_path)
    if compat_errors:
        print("Schema compatibility errors found:")
        for err in compat_errors:
            print(f" - {err}")
        sys.exit(1)
    else:
        print("Schema compatibility check passed.")
