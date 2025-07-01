#!/usr/bin/env python3
"""
Adelfa Email Client - Main Application Entry Point

A modern email client for Linux with Outlook 365 familiarity.
Designed to help Windows users transition smoothly to Linux.
"""

import sys
from pathlib import Path

# Add the adelfa package to Python path
sys.path.insert(0, str(Path(__file__).parent))

from adelfa.gui.main_window import AdelfahMainWindow
from adelfa.config.app_config import AppConfig
from adelfa.utils.logging_setup import setup_logging
from adelfa.utils.i18n import locale_manager
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QIcon


def setup_application(config: AppConfig) -> QApplication:
    """
    Set up the main QApplication with proper configuration.
    
    Args:
        config: Application configuration instance.
    
    Returns:
        QApplication: Configured application instance.
    """
    # Note: High DPI scaling is enabled by default in PyQt6
    # The old attributes AA_EnableHighDpiScaling and AA_UseHighDpiPixmaps 
    # are deprecated and no longer needed
    
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("Adelfa")
    app.setApplicationDisplayName("Adelfa Email Client")
    app.setApplicationVersion("0.1.0-dev")
    app.setOrganizationName("Adelfa Project")
    app.setOrganizationDomain("adelfa.org")
    
    # Set up internationalization and translations
    locale_manager.setup_translations(app, config.ui.language)
    
    # Set application icon (try both PNG and SVG)
    icon_paths = [
        Path(__file__).parent / "resources" / "icons" / "adelfa.png",
        Path(__file__).parent / "resources" / "icons" / "adelfa.svg"
    ]
    
    for icon_path in icon_paths:
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            break
    
    return app


def main() -> int:
    """
    Main application entry point.
    
    Returns:
        int: Exit code (0 for success, non-zero for error).
    """
    try:
        # Set up logging
        setup_logging()
        
        # Initialize application configuration
        config = AppConfig()
        
        # Create QApplication with locale support
        app = setup_application(config)
        
        # Create and show main window
        main_window = AdelfahMainWindow(config)
        main_window.show()
        
        # Start the event loop
        return app.exec()
        
    except Exception as e:
        print(f"Fatal error starting Adelfa: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main()) 