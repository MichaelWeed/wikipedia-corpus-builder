import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json_hash(obj: Any) -> str:
    """Return hex SHA-256 digest of canonical JSON serialization.

    Uses sorted keys, no whitespace separators, and UTF-8 encoding.
    """
    serialized = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_quick_hash(file_path: str | Path, size_bytes: int) -> str:
    """Compute quick_hash: hex SHA-256 over first 64 KiB || last 64 KiB || size_bytes."""
    path = Path(file_path)
    chunk_size = 64 * 1024
    hasher = hashlib.sha256()

    with path.open("rb") as f:
        first_chunk = f.read(chunk_size)
        hasher.update(first_chunk)

        if size_bytes > chunk_size:
            f.seek(max(0, size_bytes - chunk_size))
            last_chunk = f.read(chunk_size)
            hasher.update(last_chunk)
        else:
            hasher.update(b"")

    hasher.update(size_bytes.to_bytes(8, byteorder="big"))
    return hasher.hexdigest()
