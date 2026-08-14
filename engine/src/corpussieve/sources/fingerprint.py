import hashlib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from corpussieve.contracts.events import ProgressEvent
from corpussieve.contracts.hashing import canonical_json_hash, compute_quick_hash
from corpussieve.contracts.source import SourceFileInfo, SourceFingerprint
from corpussieve.sources.wikimedia.naming import parse_dump_filename


def fingerprint_files(paths: Sequence[Path]) -> SourceFingerprint:
    """Generate SourceFingerprint over a list of source dump file paths.

    Computes quick_hash for each file and hashes the canonical JSON of file metadata
    (excluding mtime) to ensure mtime changes alone do not invalidate the fingerprint.
    """
    sorted_paths = sorted(paths, key=lambda p: p.name)
    file_infos: list[SourceFileInfo] = []

    project = "unknown"
    language = "unknown"
    dump_date: str | None = None

    for path in sorted_paths:
        parts = parse_dump_filename(path.name)
        if parts:
            project = parts.project
            language = parts.language
            dump_date = parts.date

        stat = path.stat()
        size = stat.st_size
        mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat().replace("+00:00", "Z")
        qhash = compute_quick_hash(path, size)
        file_infos.append(
            SourceFileInfo(
                name=path.name,
                path=str(path),
                size_bytes=size,
                mtime_iso=mtime_iso,
                quick_hash=qhash,
            )
        )

    hashable_files = [
        {
            "name": f.name,
            "path": f.path,
            "size_bytes": f.size_bytes,
            "quick_hash": f.quick_hash,
        }
        for f in file_infos
    ]
    fp_digest = canonical_json_hash(hashable_files)

    return SourceFingerprint(
        project=project,
        language=language,
        dump_date=dump_date,
        files=file_infos,
        fingerprint=fp_digest,
        official_checksum_verified=False,
        full_hash=None,
    )


def compute_full_hash(
    paths: Sequence[Path],
    progress: Callable[[ProgressEvent], None] | None = None,
) -> str:
    """Compute full streamed SHA-256 hash over file contents in 1 MiB chunks."""
    sorted_paths = sorted(paths, key=lambda p: p.name)
    hasher = hashlib.sha256()
    chunk_size = 1024 * 1024
    total_bytes = sum(p.stat().st_size for p in sorted_paths)
    processed_bytes = 0

    for path in sorted_paths:
        with path.open("rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
                processed_bytes += len(chunk)
                if progress:
                    progress(
                        ProgressEvent(
                            job_id="fingerprint",
                            stage="full_hash",
                            completed_units=processed_bytes,
                            total_units=total_bytes,
                            message=f"Hashing {path.name}",
                        )
                    )

    return hasher.hexdigest()


def fingerprints_match(a: SourceFingerprint | str, b: SourceFingerprint | str) -> bool:
    """Return True if fingerprint digests match."""
    digest_a = a.fingerprint if isinstance(a, SourceFingerprint) else a
    digest_b = b.fingerprint if isinstance(b, SourceFingerprint) else b
    return digest_a == digest_b
