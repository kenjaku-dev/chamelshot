set -euo pipefail
VERSION="${1:-0.2.0}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPDIR="$REPO_ROOT/build/AppDir"

cd "$REPO_ROOT"
uv run pyinstaller --onedir --name snapcap \
  --paths . \
  --hidden-import config \
  --hidden-import capture \
  --hidden-import editor \
  --hidden-import overlay \
  --hidden-import preview \
  --hidden-import settings \
  --hidden-import tray \
  --hidden-import PySide6.QtWidgets \
  --hidden-import PySide6.QtGui \
  --hidden-import PySide6.QtCore \
  --hidden-import gi \
  --hidden-import dbus \
  --hidden-import dbus.mainloop.glib \
  --hidden-import dbus.service \
  --add-data "icon.png:." \
  --collect-all gi \
  --collect-all dbus \
  -y main.py

mkdir -p "$APPDIR/usr/lib/snapcap"
cp -r dist/snapcap/* "$APPDIR/usr/lib/snapcap/"
cp packaging/snapcap.desktop "$APPDIR/"
cp icon.png "$APPDIR/snapcap.png"

cat > "$APPDIR/AppRun" << 'EORUN'
#!/bin/bash
APPDIR="$(dirname "$(readlink -f "$0")")"
exec "$APPDIR/usr/lib/snapcap/snapcap" "$@"
EORUN
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/.DirIcon" << 'EODIR'
snapcap.png
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

ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$REPO_ROOT/dist/snapcap-${VERSION}-x86_64.AppImage"
echo "AppImage: dist/snapcap-${VERSION}-x86_64.AppImage"
