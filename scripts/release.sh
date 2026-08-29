#!/bin/sh
# Release: bump the version in every source of truth, regenerate .SRCINFO,
# commit and tag. Usage: scripts/release.sh X.Y.Z [--dry-run]
#
# Sources of truth kept in sync:
#   version.py           VERSION = "X.Y.Z"
#   pyproject.toml       version = "X.Y.Z"   ([project])
#   aur/PKGBUILD         pkgver=X.Y.Z
#   aur/.SRCINFO         pkgver = X.Y.Z       (regenerated via makepkg)
set -eu

NEW="${1:-}"
DRY=""
[ "${2:-}" = "--dry-run" ] && DRY=1

if ! printf '%s' "$NEW" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "usage: $0 X.Y.Z [--dry-run]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "error: tracked files modified — commit or stash first" >&2
  exit 1
fi

# Replace only the first match in pyproject.toml (the [project] version).
python3 - "$NEW" "$DRY" << 'EOF'
import re, sys, pathlib

new, dry = sys.argv[1], sys.argv[2] == "1"
edits = [
    ("version.py", r'(?m)^VERSION = "[^"]*"$', f'VERSION = "{new}"'),
    ("pyproject.toml", r'(?m)^version = "[^"]*"$', f'version = "{new}"'),
    ("aur/PKGBUILD", r"(?m)^pkgver=[^#]*$", f"pkgver={new}"),
]
for path, pattern, repl in edits:
    p = pathlib.Path(path)
    text, n = re.subn(pattern, repl, p.read_text(), count=1)
    if n != 1:
        sys.exit(f"error: pattern not found in {path}")
    if dry:
        print(f"would update {path}")
    else:
        p.write_text(text)
        print(f"updated {path}")
EOF

if [ -n "$DRY" ]; then
  echo "dry run: no files written, no commit/tag created"
  exit 0
fi

# Regenerate .SRCINFO (makepkg comes with pacman on Arch).
if command -v makepkg > /dev/null 2>&1; then
  (cd aur && makepkg --printsrcinfo > .SRCINFO)
  echo "regenerated aur/.SRCINFO"
else
  echo "warning: makepkg not found — aur/.SRCINFO NOT regenerated; fix manually" >&2
fi

VERSIONS="$(python3 scripts/check_version.py)"
echo "$VERSIONS"

git add version.py pyproject.toml aur/PKGBUILD aur/.SRCINFO
git commit -m "release: bump to $NEW"
git tag -f "v$NEW"
echo
echo "done. push with:  git push && git push -f origin v$NEW"
echo "AUR: copy aur/PKGBUILD + aur/.SRCINFO into the AUR clone, commit, push."
