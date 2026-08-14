import json
from collections.abc import Sequence
from pathlib import Path

import zstandard as zstd

from corpussieve.contracts.manifest import ManifestRecord


def write_manifest(records: Sequence[ManifestRecord], path: Path | str) -> None:
    """Write list of ManifestRecords as zstd compressed JSONL file (level 10)."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    cctx = zstd.ZstdCompressor(level=10)
    lines: list[bytes] = []

    for r in records:
        data = r.model_dump(mode="json")
        json_bytes = json.dumps(data, sort_keys=True).encode("utf-8") + b"\n"
        lines.append(json_bytes)

    raw_payload = b"".join(lines)
    compressed = cctx.compress(raw_payload)
    p.write_bytes(compressed)


def read_manifest(path: Path | str) -> list[ManifestRecord]:
    """Read zstd compressed JSONL manifest into list of ManifestRecords."""
    p = Path(path).resolve()
    compressed = p.read_bytes()
    dctx = zstd.ZstdDecompressor()
    decompressed = dctx.decompress(compressed)

    records: list[ManifestRecord] = []
    for line in decompressed.decode("utf-8").splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        data = json.loads(line_str)
        records.append(ManifestRecord.model_validate(data))

    return records
