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
        # Determine database path (always use user data directory)
        # This ensures consistent data location in both development and production
        data_dir = Path.home() / ".local" / "share" / "adelfa"
        
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
        # Set up logging (disable console output in AppImage to prevent flash)
        is_appimage = os.getenv('ADELFA_APPIMAGE') == '1' or os.getenv('APPDIR') is not None
        
        # Set Qt environment variables to prevent screen buffer issues
        if is_appimage:
            # Comprehensive dual-monitor fixes
            os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
            os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'
            os.environ['QT_QPA_PLATFORM'] = 'xcb:force-xinerama'
            os.environ['QT_X11_NO_MITSHM'] = '1'  # Prevents screen buffer sharing issues
            os.environ['QT_XCB_GL_INTEGRATION'] = 'none'  # Disable OpenGL
            os.environ['QT_QUICK_BACKEND'] = 'software'  # Force software rendering
            os.environ['QT_SCREEN_SCALE_FACTORS'] = ''  # Clear scale factors
            
        setup_logging(console_output=not is_appimage)
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
        
        # For AppImage, create a splash screen to prevent screen buffer flash
        splash = None
        if is_appimage:
            from PyQt6.QtWidgets import QSplashScreen
            from PyQt6.QtGui import QPixmap, QPainter
            from PyQt6.QtCore import Qt
            
            # Create a solid color splash screen to cover any buffer flash
            splash_pixmap = QPixmap(800, 600)
            splash_pixmap.fill(Qt.GlobalColor.white)  # Solid white background
            
            # Add simple text
            painter = QPainter(splash_pixmap)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(splash_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Loading Adelfa...")
            painter.end()
            
            splash = QSplashScreen(splash_pixmap)
            splash.show()
            app.processEvents()  # Ensure splash is displayed immediately
        
        # Create main window but don't show it yet
        main_window = AdelfahMainWindow(config, session)
        
        if is_appimage and splash:
            # Give splash screen time to fully display and Qt to initialize
            from PyQt6.QtCore import QTimer
            def show_main_window():
                if splash:
                    splash.close()
                main_window.show()
                # Maximize window after a brief delay to ensure proper initialization
                def maximize_window():
                    main_window.setWindowState(Qt.WindowState.WindowMaximized)
                QTimer.singleShot(100, maximize_window)
            QTimer.singleShot(1000, show_main_window)  # Show after 1 second
        else:
            # Normal development mode
            main_window.show()
            
            # Maximize window after it's shown and event loop has started
            from PyQt6.QtCore import QTimer
            def maximize_window():
                main_window.setWindowState(Qt.WindowState.WindowMaximized)
            QTimer.singleShot(100, maximize_window)
        
        logger.info("Application started successfully")
        
        # Start the event loop
        return app.exec()
        
    except Exception as e:
        error_msg = f"Fatal error starting Adelfa: {e}"
        # Only print to stderr if not running as AppImage (to prevent console flash)
        is_appimage = os.getenv('ADELFA_APPIMAGE') == '1' or os.getenv('APPDIR') is not None
        if not is_appimage:
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
                # Only print to stderr if not running as AppImage (to prevent console flash)
                is_appimage = os.getenv('ADELFA_APPIMAGE') == '1' or os.getenv('APPDIR') is not None
                if not is_appimage:
                    print(f"Error closing database session: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main()) 