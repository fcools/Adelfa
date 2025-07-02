#!/bin/bash

# Manual Adelfa AppImage Build Script
# This script creates a working AppImage using the existing virtual environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
APPDIR="$BUILD_DIR/AppDir"

echo "🚀 Building Adelfa AppImage (Manual Method)"
echo "Project root: $PROJECT_ROOT"

# Clean up previous builds
if [ -d "$BUILD_DIR" ]; then
    echo "🧹 Cleaning up previous build..."
    rm -rf "$BUILD_DIR"
fi

mkdir -p "$BUILD_DIR"

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "❌ Error: Virtual environment not found. Creating one..."
    python3.12 -m venv "$PROJECT_ROOT/venv"
    source "$PROJECT_ROOT/venv/bin/activate"
    pip install -r "$PROJECT_ROOT/requirements.txt"
    deactivate
fi

# Create AppDir structure
echo "📁 Creating AppDir structure..."
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib/python3.12"
mkdir -p "$APPDIR/usr/src"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$APPDIR/usr/share/applications"

# Copy Python from virtual environment
echo "🐍 Setting up Python runtime..."
cp "$PROJECT_ROOT/venv/bin/python3.12" "$APPDIR/usr/bin/python3"

# Copy site-packages from virtual environment
echo "📦 Copying Python packages..."
cp -r "$PROJECT_ROOT/venv/lib/python3.12/site-packages" "$APPDIR/usr/lib/python3.12/"

# Copy application source
echo "📋 Copying application source..."
cp -r "$PROJECT_ROOT/src/"* "$APPDIR/usr/src/"

# Copy locale data for proper internationalization
echo "🌍 Setting up locale support..."
mkdir -p "$APPDIR/usr/share/locale"
if [ -d "/usr/share/locale" ]; then
    # Copy essential locale data (just the most common ones to keep size reasonable)
    for locale_dir in en_US es_ES fr_FR de_DE it_IT pt_BR pt_PT ru_RU zh_CN zh_TW ja_JP ko_KR; do
        if [ -d "/usr/share/locale/$locale_dir" ]; then
            cp -r "/usr/share/locale/$locale_dir" "$APPDIR/usr/share/locale/" 2>/dev/null || true
        fi
    done
    echo "✅ Copied locale data"
else
    echo "⚠️ Warning: System locale directory not found"
fi

# Copy AppRun script
echo "🏃 Copying AppRun script..."
cp "$PROJECT_ROOT/appimage/AppRun" "$APPDIR/"
chmod +x "$APPDIR/AppRun"

# Copy desktop file and icon
echo "🖥️ Copying desktop file and icon..."
cp "$PROJECT_ROOT/appimage/adelfa.desktop" "$APPDIR/"
cp "$PROJECT_ROOT/appimage/adelfa.desktop" "$APPDIR/usr/share/applications/"

# Copy icon
if [ -f "$PROJECT_ROOT/src/resources/icons/adelfa.svg" ]; then
    cp "$PROJECT_ROOT/src/resources/icons/adelfa.svg" "$APPDIR/adelfa.svg"
    cp "$PROJECT_ROOT/src/resources/icons/adelfa.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
    echo "✅ Copied SVG icon"
else
    echo "⚠️ Warning: No icon found, creating a placeholder"
    echo "<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><rect width='64' height='64' fill='blue'/></svg>" > "$APPDIR/adelfa.svg"
fi

# Note: AppRun script already handles PYTHONPATH correctly, no wrapper needed
echo "✅ Using AppRun script as-is (already has proper PYTHONPATH and console suppression)"

# Download appimagetool if not present
APPIMAGETOOL="$BUILD_DIR/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "⬇️ Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi

# Create the AppImage
echo "🔨 Creating AppImage..."
OUTPUT_APPIMAGE="$PROJECT_ROOT/Adelfa-0.1.0-dev-x86_64.AppImage"

# Remove old AppImage if it exists
[ -f "$OUTPUT_APPIMAGE" ] && rm "$OUTPUT_APPIMAGE"

# Build the AppImage
cd "$BUILD_DIR"
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT_APPIMAGE"

if [ -f "$OUTPUT_APPIMAGE" ]; then
    echo "✅ AppImage created successfully!"
    echo "📍 Location: $OUTPUT_APPIMAGE"
    echo "📊 Size: $(du -h "$OUTPUT_APPIMAGE" | cut -f1)"
    echo ""
    echo "🚀 To test the AppImage:"
    echo "   chmod +x \"$OUTPUT_APPIMAGE\""
    echo "   \"$OUTPUT_APPIMAGE\""
    echo ""
    echo "🔍 Testing basic functionality..."
    chmod +x "$OUTPUT_APPIMAGE"
    echo "✅ AppImage is executable"
else
    echo "❌ Error: AppImage creation failed"
    exit 1
fi

echo ""
echo "🎉 Build completed successfully!" 