#!/bin/bash
set -e

APP=chamelshot
VERSION=4.1.0
DIST_DIR="$(dirname "$0")/dist"
BIN_DIR="${HOME}/.local/bin"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
APP_DIR="${HOME}/.local/share/applications"
APPDIR="${HOME}/Applications"

mkdir -p "$BIN_DIR" "$ICON_DIR" "$APP_DIR" "$APPDIR"

# Install AppImage
cp "$DIST_DIR/${APP}-${VERSION}-x86_64.AppImage" "$APPDIR/${APP}.AppImage"
chmod +x "$APPDIR/${APP}.AppImage"
ln -sf "$APPDIR/${APP}.AppImage" "$BIN_DIR/${APP}"

# Install icon
cp icon.png "$ICON_DIR/${APP}.png"

# Install .desktop file (points to AppImage in ~/Applications)
cat > "$APP_DIR/${APP}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=ChamelShot
Comment=Lightweight screenshot capture tool for Wayland
Exec=${APPDIR}/${APP}.AppImage
Icon=${APP}
Categories=Utility;Graphics;
Terminal=false
StartupNotify=false
EOF

echo "Installed. You may need to run:"
echo "  update-desktop-database ~/.local/share/applications"
echo
echo "Then launch from app menu or run: ${BIN_DIR}/${APP}"
