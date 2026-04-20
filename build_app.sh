#!/bin/bash
# Build TimeSlip as a macOS .app and DMG
set -e
echo "=== TimeSlip — Mac App Builder ==="

pip install pyinstaller --quiet

rm -rf build dist

echo "Building .app bundle..."
pyinstaller AutotaskTimeEntry.spec --noconfirm

echo ""
echo "Building DMG..."
hdiutil create \
  -volname "TimeSlip" \
  -srcfolder "dist/TimeSlip.app" \
  -ov -format UDZO \
  "dist/TimeSlip.dmg"

echo ""
echo "=== Build complete ==="
echo "App:  dist/TimeSlip.app"
echo "DMG:  dist/TimeSlip.dmg"
echo ""
echo "Install: cp -r dist/TimeSlip.app /Applications/"
echo "Note: On first launch right-click → Open to bypass Gatekeeper."
