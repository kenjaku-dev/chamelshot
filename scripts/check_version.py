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


def sources() -> dict[str, str | None]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    aur_pkgbuild = (ROOT / "aur" / "PKGBUILD").read_text()
    aur_srcinfo = (ROOT / "aur" / ".SRCINFO").read_text()
    return {
        "version.py": re.search(r'(?m)^VERSION = "([^"]+)"$', (ROOT / "version.py").read_text()),
        "pyproject.toml": None,  # filled below
        "aur/PKGBUILD": re.search(r"(?m)^pkgver=([^#\n]+)$", aur_pkgbuild),
        "aur/.SRCINFO": re.search(r"(?m)^[ \t]*pkgver = ([^\n]+)$", aur_srcinfo),
    } | {"pyproject.toml": pyproject.get("project", {}).get("version")}


def main() -> int:
    versions = {k: (v.group(1) if isinstance(v, re.Match) else v) for k, v in sources().items()}
    missing = [k for k, v in versions.items() if not v]
    if missing:
        print(f"FAIL: could not read version from: {', '.join(missing)}", file=sys.stderr)
        return 1
    distinct = sorted(set(versions.values()))
    for name, ver in versions.items():
        print(f"{name}: {ver}")
    if len(distinct) > 1:
        print(f"FAIL: version mismatch: {distinct}", file=sys.stderr)
        return 1
    print(f"OK: all sources agree on {distinct[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
