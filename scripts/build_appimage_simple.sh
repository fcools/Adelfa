#!/bin/bash

# Simple Adelfa AppImage Build Script using AppImageBuilder
# This script provides an easier way to build the AppImage

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Building Adelfa AppImage (Simple Method)"

# Check if appimage-builder is installed
if ! command -v appimage-builder &> /dev/null; then
    echo "📦 Installing appimage-builder..."
    if command -v pip3 &> /dev/null; then
        pip3 install --user appimage-builder
    else
        echo "❌ Error: pip3 not found. Please install Python 3 and pip first."
        exit 1
    fi
fi

# Create Python requirements file for AppImageBuilder
echo "📝 Creating requirements.txt for AppImageBuilder..."
cat > "$PROJECT_ROOT/appimage/requirements.txt" << EOF
PyQt6>=6.6.0
pydantic>=2.5.0
toml>=0.10.2
keyring>=24.3.0
cryptography>=41.0.0
beautifulsoup4>=4.12.0
Pillow>=10.1.0
python-dateutil>=2.8.2
EOF

# Set up the build environment
echo "🔧 Setting up build environment..."
cd "$PROJECT_ROOT/appimage"

# Install Python dependencies locally for the build
echo "📦 Installing Python dependencies..."
pip3 install --target ./python-packages -r requirements.txt

# Make AppRun executable
chmod +x AppRun

# Build the AppImage
echo "🔨 Building AppImage with appimage-builder..."
appimage-builder --recipe AppImageBuilder.yml

echo "✅ AppImage build completed!"

# Check if the AppImage was created
APPIMAGE_FILE="$PROJECT_ROOT/appimage/Adelfa-0.1.0-dev-x86_64.AppImage"
if [ -f "$APPIMAGE_FILE" ]; then
    # Move to project root
    mv "$APPIMAGE_FILE" "$PROJECT_ROOT/"
    echo "📍 AppImage location: $PROJECT_ROOT/Adelfa-0.1.0-dev-x86_64.AppImage"
    echo "📊 Size: $(du -h "$PROJECT_ROOT/Adelfa-0.1.0-dev-x86_64.AppImage" | cut -f1)"
    echo ""
    echo "🚀 To test the AppImage:"
    echo "   chmod +x \"$PROJECT_ROOT/Adelfa-0.1.0-dev-x86_64.AppImage\""
    echo "   \"$PROJECT_ROOT/Adelfa-0.1.0-dev-x86_64.AppImage\""
else
    echo "❌ Error: AppImage was not created successfully"
    exit 1
fi 