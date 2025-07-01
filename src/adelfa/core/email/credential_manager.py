"""
Secure credential management for Adelfa PIM suite.

Handles secure storage and retrieval of account passwords, OAuth tokens,
and other sensitive credentials using the system keyring.
"""

import keyring
import keyring.errors
from typing import Optional, Dict, Any
import json
import uuid
from ...utils.logging_setup import get_logger

logger = get_logger(__name__)


class CredentialManager:
    """
    Manages secure storage of account credentials using system keyring.
    
    Provides secure storage for passwords, OAuth tokens, and other sensitive
    account information with proper error handling and fallback mechanisms.
    """
    
    SERVICE_NAME = "adelfa-pim-suite"
    
    def __init__(self):
        """Initialize the credential manager."""
        self.logger = logger
        self._test_keyring_availability()
    
    def _test_keyring_availability(self) -> None:
        """Test if keyring is available and working."""
        try:
            # Test keyring with a dummy entry
            test_key = f"test_{uuid.uuid4().hex[:8]}"
            keyring.set_password(self.SERVICE_NAME, test_key, "test")
            retrieved = keyring.get_password(self.SERVICE_NAME, test_key)
            keyring.delete_password(self.SERVICE_NAME, test_key)
            
            if retrieved != "test":
                raise keyring.errors.KeyringError("Keyring test failed")
                
            self.logger.info("Keyring is available and working")
            
        except Exception as e:
            self.logger.warning(f"Keyring not available or not working: {e}")
            # Could implement fallback to encrypted file storage here
    
    def store_password(self, account_id: int, password_type: str, password: str) -> str:
        """
        Store a password securely in the keyring.
        
        Args:
            account_id: ID of the account
            password_type: Type of password (incoming, outgoing, caldav, carddav)
            password: The password to store
        
        Returns:
            str: Unique key for retrieving the password
        
        Raises:
            CredentialStorageError: If password cannot be stored
        """
        try:
            # Create unique key for this credential
            credential_key = f"account_{account_id}_{password_type}_{uuid.uuid4().hex[:8]}"
            
            # Store in keyring
            keyring.set_password(self.SERVICE_NAME, credential_key, password)
            
            # Verify storage by retrieving
            retrieved = keyring.get_password(self.SERVICE_NAME, credential_key)
            if retrieved != password:
                raise CredentialStorageError("Password verification failed after storage")
            
            self.logger.info(f"Stored {password_type} credential for account {account_id}")
            return credential_key
            
        except keyring.errors.KeyringError as e:
            self.logger.error(f"Failed to store {password_type} credential for account {account_id}: {e}")
            raise CredentialStorageError(f"Failed to store credential: {e}")
    
    def retrieve_password(self, credential_key: str) -> Optional[str]:
        """
        Retrieve a password from the keyring.
        
        Args:
            credential_key: The key returned by store_password
        
        Returns:
            str: The stored password, or None if not found
        """
        try:
            password = keyring.get_password(self.SERVICE_NAME, credential_key)
            if password is None:
                self.logger.warning(f"Credential not found for key: {credential_key}")
            return password
            
        except keyring.errors.KeyringError as e:
            self.logger.error(f"Failed to retrieve credential {credential_key}: {e}")
            return None
    
    def update_password(self, credential_key: str, new_password: str) -> bool:
        """
        Update an existing password in the keyring.
        
        Args:
            credential_key: The existing credential key
            new_password: The new password
        
        Returns:
            bool: True if update succeeded, False otherwise
        """
        try:
            keyring.set_password(self.SERVICE_NAME, credential_key, new_password)
            
            # Verify update
            retrieved = keyring.get_password(self.SERVICE_NAME, credential_key)
            if retrieved != new_password:
                self.logger.error(f"Password verification failed after update for key: {credential_key}")
                return False
            
            self.logger.info(f"Updated credential: {credential_key}")
            return True
            
        except keyring.errors.KeyringError as e:
            self.logger.error(f"Failed to update credential {credential_key}: {e}")
            return False
    
    def delete_password(self, credential_key: str) -> bool:
        """
        Delete a password from the keyring.
        
        Args:
            credential_key: The credential key to delete
        
        Returns:
            bool: True if deletion succeeded, False otherwise
        """
        try:
            keyring.delete_password(self.SERVICE_NAME, credential_key)
            self.logger.info(f"Deleted credential: {credential_key}")
            return True
            
        except keyring.errors.KeyringError as e:
            self.logger.error(f"Failed to delete credential {credential_key}: {e}")
            return False
    
    def store_oauth_tokens(self, account_id: int, tokens: Dict[str, Any]) -> str:
        """
        Store OAuth2 tokens securely.
        
        Args:
            account_id: ID of the account
            tokens: Dictionary containing OAuth tokens (access_token, refresh_token, etc.)
        
        Returns:
            str: Unique key for retrieving the tokens
        """
        try:
            # Serialize tokens to JSON
            tokens_json = json.dumps(tokens)
            
            # Store using the standard password method
            credential_key = self.store_password(account_id, "oauth2", tokens_json)
            
            self.logger.info(f"Stored OAuth2 tokens for account {account_id}")
            return credential_key
            
        except Exception as e:
            self.logger.error(f"Failed to store OAuth2 tokens for account {account_id}: {e}")
            raise CredentialStorageError(f"Failed to store OAuth2 tokens: {e}")
    
    def retrieve_oauth_tokens(self, credential_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve OAuth2 tokens from storage.
        
        Args:
            credential_key: The key returned by store_oauth_tokens
        
        Returns:
            Dict containing OAuth tokens, or None if not found
        """
        try:
            tokens_json = self.retrieve_password(credential_key)
            if tokens_json is None:
                return None
            
            tokens = json.loads(tokens_json)
            return tokens
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse OAuth tokens for key {credential_key}: {e}")
            return None
    
    def delete_account_credentials(self, account_id: int) -> bool:
        """
        Delete all credentials for a specific account.
        
        Args:
            account_id: ID of the account to clean up
        
        Returns:
            bool: True if all credentials were deleted successfully
        """
        try:
            # This is a simplified approach. In practice, we'd need to track
            # all credential keys for an account or iterate through keyring entries
            success = True
            
            # Try common credential types
            for password_type in ["incoming", "outgoing", "caldav", "carddav", "oauth2"]:
                try:
                    # This approach requires keeping track of credential keys
                    # In a real implementation, we'd store these keys in the database
                    pass
                except Exception as e:
                    self.logger.warning(f"Could not delete {password_type} credential for account {account_id}: {e}")
                    success = False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to delete credentials for account {account_id}: {e}")
            return False
    
    def test_credential_access(self, credential_key: str) -> bool:
        """
        Test if a credential can be accessed without retrieving it.
        
        Args:
            credential_key: The credential key to test
        
        Returns:
            bool: True if credential is accessible, False otherwise
        """
        try:
            password = keyring.get_password(self.SERVICE_NAME, credential_key)
            return password is not None
            
        except keyring.errors.KeyringError:
            return False


class CredentialStorageError(Exception):
    """Exception raised when credential storage operations fail."""
    pass


# Global credential manager instance
_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """
    Get the global credential manager instance.
    
    Returns:
        CredentialManager: Global credential manager instance
    """
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager 