"""
Application configuration management for Adelfa email client.
"""

import os
import toml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class UIConfig(BaseModel):
    """UI-specific configuration settings."""
    
    theme: str = Field(default="auto", description="UI theme: 'light', 'dark', or 'auto'")
    language: str = Field(default="auto", description="UI language: 'auto' for system, or specific locale like 'en_US', 'es_ES', 'fr_FR'")
    font_family: str = Field(default="Segoe UI", description="Default font family")
    font_size: int = Field(default=11, description="Default font size in points")
    window_width: int = Field(default=1200, description="Default window width")
    window_height: int = Field(default=800, description="Default window height")
    show_preview_pane: bool = Field(default=True, description="Show email preview pane")
    conversation_view: bool = Field(default=True, description="Enable conversation threading")


class EmailConfig(BaseModel):
    """Email-specific configuration settings."""
    
    check_interval: int = Field(default=300, description="Email check interval in seconds")
    download_attachments: bool = Field(default=False, description="Auto-download attachments")
    max_attachment_size: int = Field(default=25, description="Max attachment size in MB")
    html_email: bool = Field(default=True, description="Prefer HTML email format")
    read_receipts: bool = Field(default=False, description="Request read receipts")
    signature: str = Field(default="", description="Default email signature")


class SecurityConfig(BaseModel):
    """Security and privacy configuration settings."""
    
    remember_passwords: bool = Field(default=True, description="Store passwords in keyring")
    external_images: bool = Field(default=False, description="Load external images automatically")
    javascript_enabled: bool = Field(default=False, description="Enable JavaScript in emails")
    encryption_enabled: bool = Field(default=True, description="Enable email encryption when available")


class AppConfig:
    """
    Main application configuration class.
    
    Manages loading, saving, and accessing configuration settings from TOML files.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize application configuration.
        
        Args:
            config_dir: Custom configuration directory. If None, uses default.
        """
        self.config_dir = config_dir or self._get_default_config_dir()
        self.config_file = self.config_dir / "adelfa.toml"
        
        # Configuration sections
        self.ui = UIConfig()
        self.email = EmailConfig()
        self.security = SecurityConfig()
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing configuration
        self.load()
    
    def _get_default_config_dir(self) -> Path:
        """
        Get the default configuration directory based on the operating system.
        
        Returns:
            Path: Default configuration directory.
        """
        if os.name == "posix":  # Linux/Unix
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                return Path(xdg_config) / "adelfa"
            else:
                return Path.home() / ".config" / "adelfa"
        else:
            # Fallback for other systems
            return Path.home() / ".adelfa"
    
    def load(self) -> None:
        """
        Load configuration from TOML file.
        
        Creates default configuration if file doesn't exist.
        """
        if not self.config_file.exists():
            # Create default configuration
            self.save()
            return
        
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config_data = toml.load(f)
            
            # Load configuration sections
            if "ui" in config_data:
                self.ui = UIConfig(**config_data["ui"])
            if "email" in config_data:
                self.email = EmailConfig(**config_data["email"])
            if "security" in config_data:
                self.security = SecurityConfig(**config_data["security"])
                
        except Exception as e:
            print(f"Warning: Failed to load configuration: {e}")
            # Keep default configuration
    
    def save(self) -> None:
        """
        Save current configuration to TOML file.
        """
        config_data = {
            "ui": self.ui.model_dump(),
            "email": self.email.model_dump(),
            "security": self.security.model_dump(),
        }
        
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                toml.dump(config_data, f)
        except Exception as e:
            print(f"Warning: Failed to save configuration: {e}")
    
    def get_data_dir(self) -> Path:
        """
        Get the data directory for storing emails and databases.
        
        Returns:
            Path: Data directory path.
        """
        if os.name == "posix":  # Linux/Unix
            xdg_data = os.environ.get("XDG_DATA_HOME")
            if xdg_data:
                data_dir = Path(xdg_data) / "adelfa"
            else:
                data_dir = Path.home() / ".local" / "share" / "adelfa"
        else:
            # Fallback for other systems
            data_dir = Path.home() / ".adelfa" / "data"
        
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    
    def get_cache_dir(self) -> Path:
        """
        Get the cache directory for temporary files.
        
        Returns:
            Path: Cache directory path.
        """
        if os.name == "posix":  # Linux/Unix
            xdg_cache = os.environ.get("XDG_CACHE_HOME")
            if xdg_cache:
                cache_dir = Path(xdg_cache) / "adelfa"
            else:
                cache_dir = Path.home() / ".cache" / "adelfa"
        else:
            # Fallback for other systems
            cache_dir = Path.home() / ".adelfa" / "cache"
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir 