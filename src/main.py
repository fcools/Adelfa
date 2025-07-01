#!/usr/bin/env python3
"""
Adelfa Email Client - Main Application Entry Point

A modern email client for Linux with Outlook 365 familiarity.
Designed to help Windows users transition smoothly to Linux.
"""

import sys
import os
from pathlib import Path

# Add the adelfa package to Python path
sys.path.insert(0, str(Path(__file__).parent))

from adelfa.gui.main_window import AdelfahMainWindow
from adelfa.config.app_config import AppConfig
from adelfa.utils.logging_setup import setup_logging, get_logger
from adelfa.utils.i18n import locale_manager
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QIcon

# Database imports
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from adelfa.data.models.accounts import Base


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
    
    # Set application icon (try different locations)
    icon_paths = []
    
    # Check if we're running in AppImage
    if os.getenv('APPDIR'):
        appdir = os.getenv('APPDIR')
        icon_paths.extend([
            Path(appdir) / "adelfa.png",
            Path(appdir) / "adelfa.svg",
            Path(appdir) / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps" / "adelfa.svg"
        ])
    
    # Development paths
    icon_paths.extend([
        Path(__file__).parent / "resources" / "icons" / "adelfa.png",
        Path(__file__).parent / "resources" / "icons" / "adelfa.svg"
    ])
    
    for icon_path in icon_paths:
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            break
    
    return app


def setup_database() -> sessionmaker:
    """
    Set up the database and return a session factory.
    
    Returns:
        sessionmaker: Database session factory.
    """
    logger = get_logger(__name__)
    
    try:
        # Determine database path (use user data directory)
        if os.getenv('ADELFA_APPIMAGE'):
            # For AppImage, store in user's home directory
            data_dir = Path.home() / ".local" / "share" / "adelfa"
        else:
            # For development, store in project directory
            data_dir = Path(__file__).parent.parent / "data"
        
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "adelfa.db"
        
        logger.info(f"Using database at: {db_path}")
        
        # Create database engine
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        
        # Create all tables
        Base.metadata.create_all(engine)
        
        # Create session factory
        Session = sessionmaker(bind=engine)
        
        logger.info("Database initialized successfully")
        return Session
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def main() -> int:
    """
    Main application entry point.
    
    Returns:
        int: Exit code (0 for success, non-zero for error).
    """
    app = None
    session = None
    
    try:
        # Set up logging
        setup_logging()
        logger = get_logger(__name__)
        logger.info("Starting Adelfa Personal Information Manager...")
        
        # Initialize application configuration
        config = AppConfig()
        
        # Create QApplication with locale support
        app = setup_application(config)
        
        # Set up database
        try:
            Session = setup_database()
            session = Session()
            logger.info("Database session created successfully")
        except Exception as db_error:
            logger.error(f"Database initialization failed: {db_error}")
            QMessageBox.critical(
                None,
                "Database Error",
                f"Failed to initialize database:\n{str(db_error)}\n\n"
                "The application will run with limited functionality."
            )
            session = None
        
        # Create and show main window
        main_window = AdelfahMainWindow(config, session)
        main_window.show()
        
        # Maximize window after it's shown and event loop has started
        from PyQt6.QtCore import QTimer, Qt
        def maximize_window():
            main_window.setWindowState(Qt.WindowState.WindowMaximized)
        QTimer.singleShot(100, maximize_window)
        
        logger.info("Application started successfully")
        
        # Start the event loop
        return app.exec()
        
    except Exception as e:
        error_msg = f"Fatal error starting Adelfa: {e}"
        print(error_msg, file=sys.stderr)
        
        if app:
            QMessageBox.critical(
                None,
                "Fatal Error",
                f"Adelfa failed to start:\n{str(e)}"
            )
        
        return 1
        
    finally:
        # Clean up database session
        if session:
            try:
                session.close()
            except Exception as e:
                print(f"Error closing database session: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main()) 