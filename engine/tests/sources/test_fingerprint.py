import os
import time
from pathlib import Path

from corpussieve.sources.fingerprint import (
    compute_full_hash,
    fingerprint_files,
    fingerprints_match,
)

FIXWIKI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fixwiki"


def test_fingerprint_stability() -> None:
    files = list(FIXWIKI_DIR.glob("fixwiki*"))
    fp1 = fingerprint_files(files)
    fp2 = fingerprint_files(files)

    assert fp1.fingerprint == fp2.fingerprint
    assert fingerprints_match(fp1, fp2) is True


def test_fingerprint_changes_on_content_change(tmp_path: Path) -> None:
    # Copy a file to tmp_path
    src_file = FIXWIKI_DIR / "fixwiki-20260801-pages-articles.xml.bz2"
    dst_file = tmp_path / src_file.name
    content = bytearray(src_file.read_bytes())
    dst_file.write_bytes(bytes(content))

    fp_orig = fingerprint_files([dst_file])

    # Flip one byte
    content[0] ^= 0xFF
    dst_file.write_bytes(bytes(content))

    fp_modified = fingerprint_files([dst_file])

    assert fp_orig.fingerprint != fp_modified.fingerprint
    assert fingerprints_match(fp_orig, fp_modified) is False


def test_mtime_change_does_not_change_fingerprint(tmp_path: Path) -> None:
    src_file = FIXWIKI_DIR / "fixwiki-20260801-pages-articles.xml.bz2"
    dst_file = tmp_path / src_file.name
    dst_file.write_bytes(src_file.read_bytes())

    fp1 = fingerprint_files([dst_file])

    # Change mtime of dst_file by 100 seconds into future
    new_mtime = time.time() + 100.0
    os.utime(dst_file, (new_mtime, new_mtime))

    fp2 = fingerprint_files([dst_file])

    assert fp1.fingerprint == fp2.fingerprint
    assert fp1.files[0].mtime_iso != fp2.files[0].mtime_iso


def test_compute_full_hash() -> None:
    files = list(FIXWIKI_DIR.glob("fixwiki*"))
    hash1 = compute_full_hash(files)
    hash2 = compute_full_hash(files)

    assert len(hash1) == 64
    assert hash1 == hash2
