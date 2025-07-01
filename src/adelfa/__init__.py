"""
Adelfa Email Client

A modern email client for Linux with Outlook 365 familiarity.
Designed to help Windows users transition smoothly to Linux.

Author: Adelfa Project
License: GPL v3.0
Version: 0.1.0-dev
"""

__version__ = "0.1.0-dev"
__author__ = "Adelfa Project"
__email__ = "contact@adelfa.org"
__license__ = "GPL v3.0"
__description__ = "Modern email client for Linux with Outlook 365 familiarity"

# Package level imports for convenience
from .config.app_config import AppConfig
from .utils.logging_setup import setup_logging

__all__ = [
    "AppConfig",
    "setup_logging",
] 