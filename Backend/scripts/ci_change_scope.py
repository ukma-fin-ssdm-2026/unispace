"""Classify PR changes. Prepared with CLaude; verify through tests and review."""

import sys
from pathlib import Path

ROOT_DOCS = {"README.md", "TeamCharter.md", "CHANGELOG.md", "Project-Description.md", "AGENTS.md"}


def requires_full_ci(paths):
    if not paths:
        return True
    for path in paths:
        if path == "docs/api/openapi-generated.yaml":
            return True
        if path in ROOT_DOCS or path.startswith("docs/"):
            continue
        if path.startswith("Labs/") and Path(path).match("video_*.txt"):
            continue
        return True
    return False


def main():
    raw = Path(sys.argv[1]).read_bytes()
    paths = [part.decode("utf-8", errors="surrogateescape") for part in raw.split(b"\0") if part]
    print(f"run_full={str(requires_full_ci(paths)).lower()}")


if __name__ == "__main__":
    main()
