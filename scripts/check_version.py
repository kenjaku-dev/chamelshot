#!/usr/bin/env python3
"""Fail unless every version source of truth reports the same X.Y.Z.

Sources: version.py, pyproject.toml ([project] version), aur/PKGBUILD
(pkgver=) and aur/.SRCINFO (pkgver =). Run by CI (version-check job) and by
scripts/release.sh after a bump.
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_versions() -> dict[str, str]:
    """Return {source_name: version} for every source of truth."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

    def match(path: Path, pattern: str) -> str:
        found = re.search(pattern, path.read_text())
        if not found:
            raise SystemExit(f"FAIL: no version match in {path.relative_to(ROOT)}")
        return found.group(1)

    return {
        "version.py": match(ROOT / "version.py", r'(?m)^VERSION = "([^"]+)"$'),
        "pyproject.toml": str(pyproject.get("project", {}).get("version", "")),
        "aur/PKGBUILD": match(ROOT / "aur" / "PKGBUILD", r"(?m)^pkgver=([^#\n]+)$"),
        "aur/.SRCINFO": match(ROOT / "aur" / ".SRCINFO", r"(?m)^[ \t]*pkgver = ([^\n]+)$"),
    }


def main() -> int:
    versions = read_versions()
    for name, ver in versions.items():
        print(f"{name}: {ver}")
    distinct = sorted(set(versions.values()))
    if len(distinct) > 1:
        print(f"FAIL: version mismatch: {distinct}", file=sys.stderr)
        return 1
    print(f"OK: all sources agree on {distinct[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
