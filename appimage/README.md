# Adelfa AppImage Build Instructions

This directory contains the configuration and scripts needed to build Adelfa as an AppImage for Linux distribution.

## Console Flash Fix

The AppImage has been optimized to prevent the brief console/Python code window that could appear when launching. This is achieved through:

1. **AppRun Script Enhancement**: Direct stdout suppression in the launch script
2. **Console Logging Suppression**: When running as AppImage, console logging is disabled  
3. **Environment Variables**: `ADELFA_APPIMAGE=1` flag enables AppImage-specific behavior
4. **Error Handling**: Errors are still reported via stderr when necessary

## Files

- `AppImageBuilder.yml` - Main configuration for building the AppImage
- `AppRun` - Shell script that launches the application with console suppression
- `adelfa.desktop` - Desktop entry file for the application

## Building the AppImage

### Prerequisites

```bash
# Install appimage-builder
pip install appimage-builder

# Or using apt (Ubuntu/Debian)
sudo apt install appimage-builder
```

### Build Process

1. Navigate to the project root:
```bash
cd /path/to/Adelfa
```

2. Run the build:
```bash
cd appimage
appimage-builder --recipe AppImageBuilder.yml
```

3. The resulting AppImage will be created as `Adelfa-0.1.0-dev-x86_64.AppImage`

### Testing the AppImage

```bash
# Make executable
chmod +x Adelfa-0.1.0-dev-x86_64.AppImage

# Test run
./Adelfa-0.1.0-dev-x86_64.AppImage

# Test version
./Adelfa-0.1.0-dev-x86_64.AppImage --version
```

## Console Flash Prevention

The console flash issue has been resolved through multiple layers:

1. **AppRun Script**: Directly suppresses stdout while preserving stderr for errors
2. **Environment Setup**: Sets `ADELFA_APPIMAGE=1` to enable AppImage-specific behavior  
3. **Application Code**: Disables console logging when `ADELFA_APPIMAGE=1` is set
4. **Error Suppression**: Print statements are suppressed in AppImage mode

This ensures a clean, professional application launch without any visible console windows.

## Troubleshooting

### Build Issues

- Ensure all dependencies are installed in the build environment
- Check that `AppRun` is executable: `chmod +x AppRun`
- Verify Python 3.12 and PyQt6 are available

### Runtime Issues

- If the AppImage fails to start, check for error messages in terminal
- Ensure the AppImage is executable: `chmod +x Adelfa-*.AppImage`
- Test in different Linux distributions using the test configurations

### Console Flash Still Appears

If you still see a brief console flash:

1. Verify `ADELFA_APPIMAGE` environment variable is set in AppRun
2. Check that AppRun has proper file permissions: `chmod +x AppRun`
3. Ensure stdout redirection is working: `>/dev/null` in AppRun script

## Development vs AppImage Mode

The application automatically detects the execution environment:

- **Development Mode**: Console logging enabled, normal Python behavior
- **AppImage Mode**: Console logging disabled, stdout suppressed
- **Detection**: Based on `ADELFA_APPIMAGE` environment variable 