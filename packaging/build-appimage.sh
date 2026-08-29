set -euo pipefail
VERSION="${1:-0.2.0}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPDIR="$REPO_ROOT/build/AppDir"
INTERNAL="$REPO_ROOT/dist/chamelshot/_internal"

cd "$REPO_ROOT"
uv run pyinstaller --onedir --name chamelshot \
  --paths . \
  --hidden-import config \
  --hidden-import capture \
  --hidden-import clipboard \
  --hidden-import dispatcher \
  --hidden-import editor \
  --hidden-import history \
  --hidden-import overlay \
  --hidden-import pin \
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

# Prune what --collect-all PySide6.* drags in but the app never uses:
#   share/icons  - 1.1 GB of desktop icon themes (system themes are used at runtime)
#   share/locale - Qt translations for every locale (app is English-only)
#   Qt/translations - .qm files, same reason
rm -rf "$INTERNAL/share/icons" \
       "$INTERNAL/share/locale" \
       "$INTERNAL/PySide6/Qt/translations"

# Plugin families that drag whole dependency stacks the app never uses:
#   virtualkeyboard input-context - pulls the QML/Quick/VirtualKeyboard stack
#   libqpdf imageformat           - pulls QtPdf
#   libqgtk3 platform theme       - pulls libgtk-3, gdk-pixbuf, RAW codecs
#                                   (glycin/openraw) and a second ICU copy
rm -f "$INTERNAL"/PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so \
      "$INTERNAL"/PySide6/Qt/plugins/imageformats/libqpdf.so \
      "$INTERNAL"/PySide6/Qt/plugins/platformthemes/libqgtk3.so
rm -rf "$INTERNAL/share/themes"

# Drop shared libs nothing in the bundle references; the core Qt set and
# libpython are dlopen'd by name at startup (never linked, so ldd misses it).
NEEDED="$(mktemp)"
printf '%s\n' \
  libQt6Core.so.6 libQt6Gui.so.6 libQt6Widgets.so.6 libQt6Network.so.6 \
  libQt6DBus.so.6 libQt6OpenGL.so.6 libQt6WaylandClient.so.6 libQt6XcbQpa.so.6 \
  libQt6EglFSDeviceIntegration.so.6 libQt6EglFsKmsSupport.so.6 \
  libQt6Svg.so.6 libQt6WlShellIntegration.so.6 \
  libpython3.14.so.1.0 > "$NEEDED"
for f in "$REPO_ROOT"/dist/chamelshot/chamelshot "$INTERNAL"/PySide6/*.abi3.so \
         "$INTERNAL"/PySide6/libpyside6.abi3.so.6.11; do
  [ -e "$f" ] || continue
  ldd "$f" 2>/dev/null | grep -o "libQt6[A-Za-z]*\.so\.6" || true
done >> "$NEEDED"
find "$INTERNAL"/PySide6/Qt/plugins -name '*.so' -exec ldd {} \; 2>/dev/null \
  | grep -o "libQt6[A-Za-z]*\.so\.6" || true >> "$NEEDED"
added=1
while [ "$added" = 1 ]; do
  added=0
  for lib in "$INTERNAL"/PySide6/Qt/lib/*.so* "$INTERNAL"/lib*.so*; do
    [ -e "$lib" ] || continue
    base="$(basename "$lib")"
    grep -qx "$base" "$NEEDED" || continue
    for dep in $(ldd "$lib" 2>/dev/null | grep -o "lib[A-Za-z0-9_.-]*\.so\.[0-9]*" | sort -u); do
      if ! grep -qx "$dep" "$NEEDED"; then
        echo "$dep" >> "$NEEDED"
        added=1
      fi
    done
  done
done
for lib in "$INTERNAL"/PySide6/Qt/lib/*.so* "$INTERNAL"/lib*.so*; do
  [ -e "$lib" ] || continue
  grep -qx "$(basename "$lib")" "$NEEDED" || rm "$lib"
done
rm -f "$NEEDED"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/chamelshot"
cp -r dist/chamelshot/* "$APPDIR/usr/lib/chamelshot/"
cp packaging/chamelshot.desktop "$APPDIR/"
cp icon.png "$APPDIR/chamelshot.png"

GI_DIR="$APPDIR/usr/lib/chamelshot/girepository-1.0"
mkdir -p "$GI_DIR"
find /usr/lib /usr/lib64 -path "*girepository-1.0*" -name "*.typelib" -exec cp {} "$GI_DIR/" \; 2>/dev/null || true

cat > "$APPDIR/AppRun" << 'EORUN'
#!/bin/bash
APPDIR="$(dirname "$(readlink -f "$0")")"
export GI_TYPELIB_PATH="$APPDIR/usr/lib/chamelshot/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
exec "$APPDIR/usr/lib/chamelshot/chamelshot" "$@"
EORUN
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/.DirIcon" << 'EODIR'
chamelshot.png
EODIR

if ! command -v appimagetool &>/dev/null; then
  # Pinned to AppImageKit v12 (release "13" obsoleted the old tool; the
  # "continuous" build we used before is a moving target — never verify it).
  ARCH=$(uname -m)
  [ "$ARCH" = "x86_64" ] || { echo "no prebuilt appimagetool for $ARCH; install it manually" >&2; exit 1; }
  TOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/12/appimagetool-x86_64.AppImage"
  TOOL_SHA256="d918b4df547b388ef253f3c9e7f6529ca81a885395c31f619d9aaf7030499a13"
  APPIMAGETOOL="$REPO_ROOT/build/appimagetool"
  if [ ! -f "$APPIMAGETOOL" ]; then
    mkdir -p "$(dirname "$APPIMAGETOOL")"
    curl -fsSL "$TOOL_URL" -o "$APPIMAGETOOL"
    echo "$TOOL_SHA256  $APPIMAGETOOL" | sha256sum -c - || {
      echo "appimagetool checksum MISMATCH — refusing to use it" >&2
      rm -f "$APPIMAGETOOL"
      exit 1
    }
    chmod +x "$APPIMAGETOOL"
  fi
fi

ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$REPO_ROOT/dist/chamelshot-${VERSION}-x86_64.AppImage"
echo "AppImage: dist/chamelshot-${VERSION}-x86_64.AppImage"
