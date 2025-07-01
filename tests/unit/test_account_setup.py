"""
Unit tests for account setup functionality.

Tests the protocol detector, credential manager, and account repository
components of the email account setup system.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.adelfa.core.email.protocol_detector import ProtocolDetector, DetectionResult, ServerSettings
from src.adelfa.core.email.credential_manager import CredentialManager, CredentialStorageError
from src.adelfa.data.repositories.account_repository import AccountRepository
from src.adelfa.data.models.accounts import Base, Account, AccountType, EmailProtocol, SecurityType, AuthMethod


class TestProtocolDetector:
    """Test cases for the ProtocolDetector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ProtocolDetector()
    
    def test_gmail_detection(self):
        """Test Gmail settings detection."""
        result = self.detector.detect_settings("test@gmail.com")
        
        assert result.success
        assert result.provider_name == "Gmail"
        assert result.email_settings is not None
        assert "imap" in result.email_settings
        assert "smtp" in result.email_settings
        
        imap_settings = result.email_settings["imap"]
        assert imap_settings.server == "imap.gmail.com"
        assert imap_settings.port == 993
        assert imap_settings.security == SecurityType.TLS_SSL
        
        smtp_settings = result.email_settings["smtp"]
        assert smtp_settings.server == "smtp.gmail.com"
        assert smtp_settings.port == 587
        assert smtp_settings.security == SecurityType.STARTTLS
    
    def test_outlook_detection(self):
        """Test Outlook.com settings detection."""
        result = self.detector.detect_settings("test@outlook.com")
        
        assert result.success
        assert result.provider_name == "Outlook.com"
        assert result.email_settings is not None
        
        imap_settings = result.email_settings["imap"]
        assert imap_settings.server == "outlook.office365.com"
        assert imap_settings.port == 993
    
    def test_unknown_provider_detection(self):
        """Test detection for unknown provider."""
        # Mock the generic detection methods to avoid actual network calls
        with patch.object(self.detector, '_detect_generic_settings') as mock_generic:
            mock_generic.return_value = DetectionResult(
                success=False,
                error_message="Could not detect any server settings"
            )
            
            result = self.detector.detect_settings("test@unknown-domain.com")
            assert not result.success
            assert "Could not detect" in result.error_message
    
    def test_invalid_email_address(self):
        """Test detection with invalid email address."""
        with pytest.raises(Exception):
            self.detector.detect_settings("invalid-email")
    
    @patch('imaplib.IMAP4_SSL')
    def test_imap_connection_test(self, mock_imap):
        """Test IMAP connection testing."""
        # Mock successful connection
        mock_conn = Mock()
        mock_imap.return_value = mock_conn
        
        settings = ServerSettings("imap.example.com", 993, SecurityType.TLS_SSL, EmailProtocol.IMAP)
        success, error = self.detector.test_connection(settings, "user@example.com", "password")
        
        assert success
        assert error is None
        mock_conn.login.assert_called_once_with("user@example.com", "password")
        mock_conn.logout.assert_called_once()
    
    @patch('imaplib.IMAP4_SSL')
    def test_imap_authentication_failure(self, mock_imap):
        """Test IMAP authentication failure."""
        # Mock authentication failure
        mock_conn = Mock()
        mock_conn.login.side_effect = Exception("Authentication failed")
        mock_imap.return_value = mock_conn
        
        settings = ServerSettings("imap.example.com", 993, SecurityType.TLS_SSL, EmailProtocol.IMAP)
        success, error = self.detector.test_connection(settings, "user@example.com", "wrong_password")
        
        assert not success
        assert "Authentication failed" in error


class TestCredentialManager:
    """Test cases for the CredentialManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use a mock keyring to avoid system dependencies
        with patch('keyring.set_password'), \
             patch('keyring.get_password'), \
             patch('keyring.delete_password'):
            self.credential_manager = CredentialManager()
    
    @patch('keyring.set_password')
    @patch('keyring.get_password')
    def test_store_and_retrieve_password(self, mock_get, mock_set):
        """Test storing and retrieving a password."""
        mock_get.return_value = "test_password"
        
        # Store password
        key = self.credential_manager.store_password(1, "incoming", "test_password")
        
        assert key is not None
        assert key.startswith("account_1_incoming_")
        mock_set.assert_called_once()
        
        # Retrieve password
        password = self.credential_manager.retrieve_password(key)
        assert password == "test_password"
        mock_get.assert_called_once()
    
    @patch('keyring.set_password')
    @patch('keyring.get_password')
    def test_update_password(self, mock_get, mock_set):
        """Test updating an existing password."""
        mock_get.return_value = "new_password"
        
        key = "test_key"
        success = self.credential_manager.update_password(key, "new_password")
        
        assert success
        mock_set.assert_called_once_with(
            self.credential_manager.SERVICE_NAME, 
            key, 
            "new_password"
        )
    
    @patch('keyring.delete_password')
    def test_delete_password(self, mock_delete):
        """Test deleting a password."""
        key = "test_key"
        success = self.credential_manager.delete_password(key)
        
        assert success
        mock_delete.assert_called_once_with(
            self.credential_manager.SERVICE_NAME, 
            key
        )
    
    @patch('keyring.set_password')
    @patch('keyring.get_password')
    def test_store_oauth_tokens(self, mock_get, mock_set):
        """Test storing OAuth tokens."""
        tokens = {
            "access_token": "access_123",
            "refresh_token": "refresh_456",
            "expires_in": 3600
        }
        
        mock_get.return_value = '{"access_token": "access_123", "refresh_token": "refresh_456", "expires_in": 3600}'
        
        key = self.credential_manager.store_oauth_tokens(1, tokens)
        
        assert key is not None
        mock_set.assert_called_once()
        
        # Retrieve tokens
        retrieved_tokens = self.credential_manager.retrieve_oauth_tokens(key)
        assert retrieved_tokens == tokens
    
    @patch('keyring.set_password')
    def test_keyring_error_handling(self, mock_set):
        """Test error handling when keyring operations fail."""
        mock_set.side_effect = Exception("Keyring not available")
        
        with pytest.raises(CredentialStorageError):
            self.credential_manager.store_password(1, "incoming", "password")


class TestAccountRepository:
    """Test cases for the AccountRepository class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Mock the credential manager
        with patch('src.adelfa.data.repositories.account_repository.get_credential_manager') as mock_cm:
            self.mock_credential_manager = Mock()
            mock_cm.return_value = self.mock_credential_manager
            self.repository = AccountRepository(self.session)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.session.close()
    
    def test_create_account(self):
        """Test creating a new account."""
        self.mock_credential_manager.store_password.return_value = "test_key_123"
        
        account_data = {
            "name": "Test Account",
            "email_address": "test@example.com",
            "display_name": "Test User",
            "incoming_server": "imap.example.com",
            "incoming_port": 993,
            "incoming_username": "test@example.com",
            "incoming_password": "password123",
            "outgoing_server": "smtp.example.com",
            "outgoing_port": 587,
            "outgoing_username": "test@example.com",
            "outgoing_password": "password123"
        }
        
        account = self.repository.create_account(account_data)
        
        assert account is not None
        assert account.name == "Test Account"
        assert account.email_address == "test@example.com"
        assert account.incoming_server == "imap.example.com"
        assert account.outgoing_server == "smtp.example.com"
        
        # Check that credentials were stored
        assert self.mock_credential_manager.store_password.call_count == 2  # incoming and outgoing
    
    def test_get_account_by_email(self):
        """Test retrieving an account by email address."""
        # Create test account
        account = Account(
            name="Test Account",
            email_address="test@example.com"
        )
        self.session.add(account)
        self.session.commit()
        
        # Retrieve account
        retrieved = self.repository.get_account_by_email("test@example.com")
        
        assert retrieved is not None
        assert retrieved.email_address == "test@example.com"
    
    def test_get_all_accounts(self):
        """Test retrieving all accounts."""
        # Create test accounts
        account1 = Account(name="Account 1", email_address="test1@example.com")
        account2 = Account(name="Account 2", email_address="test2@example.com", is_enabled=False)
        
        self.session.add_all([account1, account2])
        self.session.commit()
        
        # Get all accounts
        all_accounts = self.repository.get_all_accounts(enabled_only=False)
        assert len(all_accounts) == 2
        
        # Get enabled accounts only
        enabled_accounts = self.repository.get_all_accounts(enabled_only=True)
        assert len(enabled_accounts) == 1
        assert enabled_accounts[0].name == "Account 1"
    
    def test_set_default_account(self):
        """Test setting a default account."""
        # Create test accounts
        account1 = Account(name="Account 1", email_address="test1@example.com")
        account2 = Account(name="Account 2", email_address="test2@example.com")
        
        self.session.add_all([account1, account2])
        self.session.commit()
        
        # Set account1 as default
        success = self.repository.set_default_account(account1.id)
        assert success
        
        # Verify default account
        default = self.repository.get_default_account()
        assert default is not None
        assert default.id == account1.id
        
        # Set account2 as default
        success = self.repository.set_default_account(account2.id)
        assert success
        
        # Verify only account2 is default
        self.session.refresh(account1)
        self.session.refresh(account2)
        assert not account1.is_default
        assert account2.is_default
    
    def test_delete_account(self):
        """Test deleting an account."""
        self.mock_credential_manager.delete_password.return_value = True
        
        # Create test account
        account = Account(
            name="Test Account",
            email_address="test@example.com",
            incoming_password_key="key123"
        )
        self.session.add(account)
        self.session.commit()
        account_id = account.id
        
        # Delete account
        success = self.repository.delete_account(account_id)
        assert success
        
        # Verify account is deleted
        deleted_account = self.repository.get_account(account_id)
        assert deleted_account is None
        
        # Verify credentials were deleted
        self.mock_credential_manager.delete_password.assert_called()
    
    def test_get_account_credentials(self):
        """Test retrieving account credentials."""
        self.mock_credential_manager.retrieve_password.return_value = "test_password"
        
        account = Account(
            name="Test Account",
            email_address="test@example.com",
            incoming_password_key="test_key_123"
        )
        
        password = self.repository.get_account_credentials(account, "incoming")
        
        assert password == "test_password"
        self.mock_credential_manager.retrieve_password.assert_called_once_with("test_key_123")
    
    def test_record_connection_test(self):
        """Test recording connection test results."""
        # Create test account
        account = Account(name="Test Account", email_address="test@example.com")
        self.session.add(account)
        self.session.commit()
        
        # Record successful test
        success = self.repository.record_connection_test(
            account.id, "incoming", True, None, 150
        )
        assert success
        
        # Verify account status was updated
        self.session.refresh(account)
        assert account.connection_status == "connected"
        assert account.last_error is None
        
        # Record failed test
        success = self.repository.record_connection_test(
            account.id, "incoming", False, "Connection timeout"
        )
        assert success
        
        # Verify account status was updated
        self.session.refresh(account)
        assert account.connection_status == "error"
        assert account.last_error == "Connection timeout"
    
    def test_get_connection_test_history(self):
        """Test retrieving connection test history."""
        # Create test account
        account = Account(name="Test Account", email_address="test@example.com")
        self.session.add(account)
        self.session.commit()
        
        # Record multiple tests
        for i in range(3):
            self.repository.record_connection_test(
                account.id, "incoming", i % 2 == 0, f"Test {i}"
            )
        
        # Get test history
        history = self.repository.get_connection_test_history(account.id)
        
        assert len(history) == 3
        # Should be ordered by most recent first
        assert history[0].error_message == "Test 2"


if __name__ == "__main__":
    pytest.main([__file__]) 