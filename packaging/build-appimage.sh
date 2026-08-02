set -euo pipefail
VERSION="${1:-0.2.0}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPDIR="$REPO_ROOT/build/AppDir"

cd "$REPO_ROOT"
uv run pyinstaller --onedir --name chamelshot \
  --paths . \
  --hidden-import config \
  --hidden-import capture \
  --hidden-import editor \
  --hidden-import overlay \
  --hidden-import preview \
  --hidden-import proc \
  --hidden-import settings \
  --hidden-import tray \
  --hidden-import PySide6.QtCore \
  --hidden-import PySide6.QtGui \
  --hidden-import PySide6.QtWidgets \
  --hidden-import shiboken6 \
  --hidden-import gi \
  --hidden-import dbus \
  --hidden-import dbus.mainloop.glib \
  --hidden-import dbus.service \
  --add-data "icon.png:." \
  --collect-all PySide6.QtCore \
  --collect-all PySide6.QtGui \
  --collect-all PySide6.QtWidgets \
  --collect-all gi \
  --collect-all dbus \
  -y main.py

mkdir -p "$APPDIR/usr/lib/chamelshot"
cp -r dist/chamelshot/* "$APPDIR/usr/lib/chamelshot/"
cp packaging/chamelshot.desktop "$APPDIR/"
cp icon.png "$APPDIR/chamelshot.png"

cat > "$APPDIR/AppRun" << 'EORUN'
#!/bin/bash
APPDIR="$(dirname "$(readlink -f "$0")")"
exec "$APPDIR/usr/lib/chamelshot/chamelshot" "$@"
EORUN
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/.DirIcon" << 'EODIR'
chamelshot.png
EODIR

if ! command -v appimagetool &>/dev/null; then
  ARCH=$(uname -m)
  APPIMAGETOOL="$REPO_ROOT/build/appimagetool"
  if [ ! -f "$APPIMAGETOOL" ]; then
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage" -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
  fi
  APPIMAGETOOL="$APPIMAGETOOL"
fi

ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$REPO_ROOT/dist/chamelshot-${VERSION}-x86_64.AppImage"
echo "AppImage: dist/chamelshot-${VERSION}-x86_64.AppImage"
