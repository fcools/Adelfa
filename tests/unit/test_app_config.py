"""
Unit tests for application configuration.
"""

import tempfile
import pytest
from pathlib import Path

from adelfa.config.app_config import AppConfig, UIConfig, EmailConfig, SecurityConfig


class TestUIConfig:
    """Test UIConfig model."""
    
    def test_default_values(self):
        """Test UIConfig default values."""
        config = UIConfig()
        assert config.theme == "auto"
        assert config.font_family == "Segoe UI"
        assert config.font_size == 11
        assert config.window_width == 1200
        assert config.window_height == 800
        assert config.show_preview_pane is True
        assert config.conversation_view is True
    
    def test_custom_values(self):
        """Test UIConfig with custom values."""
        config = UIConfig(
            theme="dark",
            font_family="Arial",
            font_size=12,
            window_width=1400,
            window_height=900
        )
        assert config.theme == "dark"
        assert config.font_family == "Arial"
        assert config.font_size == 12
        assert config.window_width == 1400
        assert config.window_height == 900


class TestEmailConfig:
    """Test EmailConfig model."""
    
    def test_default_values(self):
        """Test EmailConfig default values."""
        config = EmailConfig()
        assert config.check_interval == 300
        assert config.download_attachments is False
        assert config.max_attachment_size == 25
        assert config.html_email is True
        assert config.read_receipts is False
        assert config.signature == ""


class TestSecurityConfig:
    """Test SecurityConfig model."""
    
    def test_default_values(self):
        """Test SecurityConfig default values."""
        config = SecurityConfig()
        assert config.remember_passwords is True
        assert config.external_images is False
        assert config.javascript_enabled is False
        assert config.encryption_enabled is True


class TestAppConfig:
    """Test AppConfig class."""
    
    def test_initialization_with_temp_dir(self):
        """Test AppConfig initialization with temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "adelfa_test"
            config = AppConfig(config_dir=config_dir)
            
            # Check that config directory was created
            assert config.config_dir.exists()
            assert config.config_dir == config_dir
            
            # Check that config file was created
            assert config.config_file.exists()
            assert config.config_file.name == "adelfa.toml"
    
    def test_default_config_values(self):
        """Test that default configuration values are set correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "adelfa_test"
            config = AppConfig(config_dir=config_dir)
            
            # Test UI config
            assert isinstance(config.ui, UIConfig)
            assert config.ui.theme == "auto"
            assert config.ui.font_size == 11
            
            # Test email config
            assert isinstance(config.email, EmailConfig)
            assert config.email.check_interval == 300
            
            # Test security config
            assert isinstance(config.security, SecurityConfig)
            assert config.security.remember_passwords is True
    
    def test_save_and_load(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "adelfa_test"
            
            # Create config and modify some values
            config1 = AppConfig(config_dir=config_dir)
            config1.ui.font_size = 14
            config1.ui.theme = "dark"
            config1.email.check_interval = 600
            config1.save()
            
            # Create new config instance and load
            config2 = AppConfig(config_dir=config_dir)
            
            # Check that values were loaded correctly
            assert config2.ui.font_size == 14
            assert config2.ui.theme == "dark"
            assert config2.email.check_interval == 600
    
    def test_get_data_dir(self):
        """Test data directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "adelfa_test"
            config = AppConfig(config_dir=config_dir)
            
            data_dir = config.get_data_dir()
            assert data_dir.exists()
            assert data_dir.is_dir()
    
    def test_get_cache_dir(self):
        """Test cache directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "adelfa_test"
            config = AppConfig(config_dir=config_dir)
            
            cache_dir = config.get_cache_dir()
            assert cache_dir.exists()
            assert cache_dir.is_dir() 