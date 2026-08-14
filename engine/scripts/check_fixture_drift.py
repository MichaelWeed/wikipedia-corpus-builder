#!/usr/bin/env python3
"""Check tests/fixtures/fixwiki for regeneration drift, content-aware for
gzip-compressed fixtures.

Run tests/fixtures/generator.py first to regenerate fixtures in place, then
run this from the `engine/` directory.

Why this exists rather than a plain `git diff --exit-code`: gzip's
compressed byte output is not guaranteed identical across zlib
versions/platforms for byte-identical *decompressed* content, even with an
explicit `mtime=0` (which the generator already passes). This was not a
theoretical concern -- it was observed in real CI: this repo's two
`.sql.gz` fixtures regenerated to different bytes on ubuntu-latest and
macos-latest in the same run, despite decompressing to identical content on
both (see qa/FINDINGS.md #11). A raw byte/git diff treats that as drift; a
real regression (the generator actually producing different *data*) would
still be caught, since decompressed content is what's compared for `.gz`
files. Non-gzip files (the `.bz2` fixtures, `expected.json`) are compared
byte-for-byte as before -- bz2 has no timestamp embedding and showed no
cross-platform drift.
"""

import gzip
import subprocess
import sys
from pathlib import Path

FIXWIKI_REL = "engine/tests/fixtures/fixwiki"


def main() -> int:
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )

    changed = [
        line
        for line in subprocess.run(
            ["git", "diff", "--name-only", "--", FIXWIKI_REL],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        ).stdout.splitlines()
        if line
    ]

    if not changed:
        print("No regeneration drift.")
        return 0

    real_drift = []
    ignored = []
    for rel_path in changed:
        committed = subprocess.run(
            ["git", "show", f"HEAD:{rel_path}"],
            capture_output=True,
            check=True,
            cwd=repo_root,
        ).stdout
        current = (repo_root / rel_path).read_bytes()

        if rel_path.endswith(".gz"):
            committed = gzip.decompress(committed)
            current = gzip.decompress(current)

        if committed != current:
            real_drift.append(rel_path)
        else:
            ignored.append(rel_path)

    if real_drift:
        print("Regeneration drift detected (content differs) in:")
        for p in real_drift:
            print(f"  {p}")
        return 1

    print(
        f"No regeneration drift: {len(ignored)} file(s) differ at the byte "
        "level (gzip compression is not guaranteed byte-identical across "
        "zlib versions/platforms) but decompressed content is identical:"
    )
    for p in ignored:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
