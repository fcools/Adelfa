#!/bin/bash

# Adelfa AppImage Build Script
# This script creates a portable AppImage for the Adelfa email client

set -e

# Configuration
APP_NAME="Adelfa"
APP_VERSION="0.1.0-dev"
ARCH="x86_64"
PYTHON_VERSION="3.12"

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
APPDIR="$BUILD_DIR/AppDir"
APPIMAGE_DIR="$PROJECT_ROOT/appimage"

echo "🚀 Building Adelfa AppImage v$APP_VERSION"
echo "Project root: $PROJECT_ROOT"

# Clean up previous builds
if [ -d "$BUILD_DIR" ]; then
    echo "🧹 Cleaning up previous build..."
    rm -rf "$BUILD_DIR"
fi

mkdir -p "$BUILD_DIR"
mkdir -p "$APPDIR"

# Check dependencies
echo "🔍 Checking dependencies..."

# Check if python3.12 is available
if ! command -v python3.12 &> /dev/null; then
    echo "❌ Error: Python 3.12 is required but not found"
    echo "Please install Python 3.12 first"
    exit 1
fi

# Check if we have a virtual environment with dependencies
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "❌ Error: Virtual environment not found at $PROJECT_ROOT/venv"
    echo "Please run: python3.12 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Create AppDir structure
echo "📁 Creating AppDir structure..."
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"
mkdir -p "$APPDIR/usr/lib/python$PYTHON_VERSION/site-packages"
mkdir -p "$APPDIR/usr/src"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$APPDIR/usr/share/applications"

# Copy application source
echo "📋 Copying application source..."
cp -r "$PROJECT_ROOT/src/"* "$APPDIR/usr/src/"

# Copy Python interpreter
echo "🐍 Copying Python interpreter..."
cp "$(which python3.12)" "$APPDIR/usr/bin/python3"

# Copy Python standard library
echo "📚 Copying Python standard library..."
PYTHON_LIB_DIR="$(python3.12 -c "import sys; print(sys.path[1])")"
cp -r "$PYTHON_LIB_DIR" "$APPDIR/usr/lib/python$PYTHON_VERSION/"

# Copy site-packages from virtual environment
echo "📦 Copying Python packages..."
cp -r "$PROJECT_ROOT/venv/lib/python$PYTHON_VERSION/site-packages/"* "$APPDIR/usr/lib/python$PYTHON_VERSION/site-packages/"

# Copy system Qt libraries and plugins
echo "🎨 Copying Qt libraries..."
QT_LIB_DIR="/usr/lib/x86_64-linux-gnu"
if [ -d "$QT_LIB_DIR" ]; then
    mkdir -p "$APPDIR/usr/lib/x86_64-linux-gnu"
    
    # Copy Qt6 libraries
    find "$QT_LIB_DIR" -name "libQt6*.so*" -exec cp {} "$APPDIR/usr/lib/x86_64-linux-gnu/" \; 2>/dev/null || true
    
    # Copy Qt plugins
    if [ -d "$QT_LIB_DIR/qt6/plugins" ]; then
        mkdir -p "$APPDIR/usr/lib/x86_64-linux-gnu/qt6"
        cp -r "$QT_LIB_DIR/qt6/plugins" "$APPDIR/usr/lib/x86_64-linux-gnu/qt6/"
    fi
fi

# Copy other required system libraries
echo "📚 Copying system libraries..."
LIBS_TO_COPY=(
    "libssl.so.3"
    "libcrypto.so.3"
    "libffi.so.8"
    "libxcb*.so*"
    "libX11.so.6"
    "libXext.so.6"
    "libXrender.so.1"
    "libfontconfig.so.1"
    "libfreetype.so.6"
)

for lib_pattern in "${LIBS_TO_COPY[@]}"; do
    find /usr/lib/x86_64-linux-gnu /lib/x86_64-linux-gnu -name "$lib_pattern" -exec cp {} "$APPDIR/usr/lib/x86_64-linux-gnu/" \; 2>/dev/null || true
done

# Copy AppRun script
echo "🏃 Copying AppRun script..."
cp "$APPIMAGE_DIR/AppRun" "$APPDIR/"
chmod +x "$APPDIR/AppRun"

# Copy desktop file
echo "🖥️ Copying desktop file..."
cp "$APPIMAGE_DIR/adelfa.desktop" "$APPDIR/"
cp "$APPIMAGE_DIR/adelfa.desktop" "$APPDIR/usr/share/applications/"

# Copy and convert icon
echo "🎨 Processing application icon..."
cp "$PROJECT_ROOT/src/resources/icons/adelfa.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
cp "$PROJECT_ROOT/src/resources/icons/adelfa.svg" "$APPDIR/adelfa.svg"

# Create PNG icon if convert is available
if command -v convert &> /dev/null; then
    convert "$APPDIR/adelfa.svg" -resize 256x256 "$APPDIR/adelfa.png"
    echo "✅ Created PNG icon"
else
    echo "⚠️ Warning: ImageMagick not found, using SVG icon only"
fi

# Download appimagetool if not present
APPIMAGETOOL="$BUILD_DIR/appimagetool"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "⬇️ Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi

# Create the AppImage
echo "🔨 Creating AppImage..."
OUTPUT_APPIMAGE="$PROJECT_ROOT/Adelfa-$APP_VERSION-$ARCH.AppImage"

# Remove old AppImage if it exists
[ -f "$OUTPUT_APPIMAGE" ] && rm "$OUTPUT_APPIMAGE"

# Build the AppImage
cd "$BUILD_DIR"
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$OUTPUT_APPIMAGE"

if [ -f "$OUTPUT_APPIMAGE" ]; then
    echo "✅ AppImage created successfully!"
    echo "📍 Location: $OUTPUT_APPIMAGE"
    echo "📊 Size: $(du -h "$OUTPUT_APPIMAGE" | cut -f1)"
    echo ""
    echo "🚀 To test the AppImage:"
    echo "   chmod +x \"$OUTPUT_APPIMAGE\""
    echo "   \"$OUTPUT_APPIMAGE\""
else
    echo "❌ Error: AppImage creation failed"
    exit 1
fi

echo ""
echo "🎉 Build completed successfully!" 