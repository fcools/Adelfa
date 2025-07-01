"""
Internationalization (i18n) utilities for Adelfa email client.

Handles system locale detection, Qt translator setup, and language configuration.
"""

import os
import locale
from pathlib import Path
from typing import Optional, List
from PyQt6.QtCore import QLocale, QTranslator, QCoreApplication
from PyQt6.QtWidgets import QApplication

from ..utils.logging_setup import get_logger


class LocaleManager:
    """
    Manages application locale and translations.
    
    Handles detection of system locale, loading Qt translations,
    and managing application language settings.
    """
    
    def __init__(self):
        """Initialize the locale manager."""
        self.logger = get_logger(__name__)
        self.translators: List[QTranslator] = []
        self.current_locale = "en_US"
        
    def detect_system_locale(self) -> str:
        """
        Detect the system's preferred locale.
        
        Returns:
            str: Locale string in format 'language_COUNTRY' (e.g., 'en_US', 'es_ES').
        """
        try:
            # Method 1: Try environment variables first (most reliable on Linux)
            for env_var in ['LC_ALL', 'LC_MESSAGES', 'LANG']:
                locale_str = os.environ.get(env_var)
                if locale_str:
                    # Parse locale string (e.g., 'en_US.UTF-8' -> 'en_US')
                    locale_clean = locale_str.split('.')[0].replace('-', '_')
                    if self._is_valid_locale(locale_clean):
                        self.logger.info(f"Detected system locale from {env_var}: {locale_clean}")
                        return locale_clean
            
            # Method 2: Use Python's locale module
            try:
                system_locale = locale.getdefaultlocale()[0]
                if system_locale:
                    locale_clean = system_locale.replace('-', '_')
                    if self._is_valid_locale(locale_clean):
                        self.logger.info(f"Detected system locale from Python: {locale_clean}")
                        return locale_clean
            except Exception as e:
                self.logger.warning(f"Failed to get locale from Python: {e}")
            
            # Method 3: Use Qt's locale detection
            qt_locale = QLocale.system()
            locale_name = qt_locale.name()  # Returns format like 'en_US'
            if self._is_valid_locale(locale_name):
                self.logger.info(f"Detected system locale from Qt: {locale_name}")
                return locale_name
            
        except Exception as e:
            self.logger.warning(f"Error detecting system locale: {e}")
        
        # Fallback to English (US)
        self.logger.info("Using fallback locale: en_US")
        return "en_US"
    
    def _is_valid_locale(self, locale_str: str) -> bool:
        """
        Check if a locale string is valid.
        
        Args:
            locale_str: Locale string to validate.
            
        Returns:
            bool: True if locale is valid, False otherwise.
        """
        if not locale_str or len(locale_str) < 2:
            return False
        
        # Check basic format (language or language_COUNTRY)
        parts = locale_str.split('_')
        if len(parts) == 1:
            # Just language code (e.g., 'en')
            return len(parts[0]) == 2 and parts[0].isalpha()
        elif len(parts) == 2:
            # Language and country (e.g., 'en_US')
            return (len(parts[0]) == 2 and parts[0].isalpha() and 
                   len(parts[1]) == 2 and parts[1].isupper())
        
        return False
    
    def setup_translations(self, app: QApplication, language: str = "auto", 
                          translations_dir: Optional[Path] = None) -> None:
        """
        Set up Qt translations for the application.
        
        Args:
            app: QApplication instance.
            language: Language to use ('auto' for system locale, or specific locale).
            translations_dir: Directory containing translation files.
        """
        # Determine the locale to use
        if language == "auto":
            target_locale = self.detect_system_locale()
        else:
            target_locale = language
        
        self.current_locale = target_locale
        self.logger.info(f"Setting up translations for locale: {target_locale}")
        
        # Set Qt locale
        qt_locale = QLocale(target_locale)
        QLocale.setDefault(qt_locale)
        
        # If no translations directory specified, use default
        if translations_dir is None:
            app_dir = Path(__file__).parent.parent.parent
            translations_dir = app_dir / "resources" / "translations"
        
        # Load Qt's built-in translations first
        self._load_qt_translations(app, target_locale)
        
        # Load application translations
        if translations_dir.exists():
            self._load_app_translations(app, target_locale, translations_dir)
        else:
            self.logger.warning(f"Translations directory not found: {translations_dir}")
    
    def _load_qt_translations(self, app: QApplication, locale_name: str) -> None:
        """
        Load Qt's built-in translations.
        
        Args:
            app: QApplication instance.
            locale_name: Locale name (e.g., 'en_US').
        """
        # Extract language code (e.g., 'en' from 'en_US')
        language_code = locale_name.split('_')[0]
        
        # Qt translation file names
        qt_translation_files = [
            f"qt_{language_code}",
            f"qtbase_{language_code}",
            f"qtmultimedia_{language_code}",
            f"qtnetwork_{language_code}"
        ]
        
        for translation_file in qt_translation_files:
            translator = QTranslator()
            
            # Try to load from Qt's translation directory
            if translator.load(translation_file, QLocale.system().name()):
                if app.installTranslator(translator):
                    self.translators.append(translator)
                    self.logger.debug(f"Loaded Qt translation: {translation_file}")
    
    def _load_app_translations(self, app: QApplication, locale_name: str, 
                              translations_dir: Path) -> None:
        """
        Load application-specific translations.
        
        Args:
            app: QApplication instance.
            locale_name: Locale name (e.g., 'en_US').
            translations_dir: Directory containing translation files.
        """
        # Look for translation file (e.g., 'adelfa_es_ES.qm')
        translation_file = translations_dir / f"adelfa_{locale_name}.qm"
        
        if not translation_file.exists():
            # Try with just language code (e.g., 'adelfa_es.qm')
            language_code = locale_name.split('_')[0]
            translation_file = translations_dir / f"adelfa_{language_code}.qm"
        
        if translation_file.exists():
            translator = QTranslator()
            if translator.load(str(translation_file)):
                if app.installTranslator(translator):
                    self.translators.append(translator)
                    self.logger.info(f"Loaded application translation: {translation_file}")
            else:
                self.logger.warning(f"Failed to load translation file: {translation_file}")
        else:
            self.logger.info(f"No translation file found for locale: {locale_name}")
    
    def get_current_locale(self) -> str:
        """
        Get the currently active locale.
        
        Returns:
            str: Current locale string.
        """
        return self.current_locale
    
    def get_supported_locales(self) -> List[str]:
        """
        Get list of supported locales.
        
        Returns:
            List[str]: List of supported locale strings.
        """
        # For now, return a basic list. In the future, this could be
        # dynamically generated based on available translation files.
        return [
            "en_US",  # English (US)
            "en_GB",  # English (UK)
            "es_ES",  # Spanish (Spain)
            "es_MX",  # Spanish (Mexico)
            "fr_FR",  # French (France)
            "de_DE",  # German (Germany)
            "it_IT",  # Italian (Italy)
            "pt_BR",  # Portuguese (Brazil)
            "pt_PT",  # Portuguese (Portugal)
            "ru_RU",  # Russian (Russia)
            "zh_CN",  # Chinese (Simplified)
            "zh_TW",  # Chinese (Traditional)
            "ja_JP",  # Japanese (Japan)
            "ko_KR",  # Korean (South Korea)
        ]


# Global locale manager instance
locale_manager = LocaleManager() 