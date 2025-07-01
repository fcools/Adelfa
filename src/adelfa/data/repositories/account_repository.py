"""
Account repository for Adelfa PIM suite.

Handles database operations for email, calendar, and contact accounts
with secure credential management integration.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, desc

from ...utils.logging_setup import get_logger
from ...core.email.credential_manager import get_credential_manager, CredentialStorageError
from ..models.accounts import Account, AccountProvider, AccountConnectionTest, AccountType

logger = get_logger(__name__)


class AccountRepository:
    """
    Repository for account operations.
    
    Provides CRUD operations for accounts with secure credential handling
    and connection test result tracking.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the account repository.
        
        Args:
            session: SQLAlchemy session instance
        """
        self.session = session
        self.credential_manager = get_credential_manager()
        self.logger = logger
    
    def create_account(self, account_data: Dict[str, Any]) -> Optional[Account]:
        """
        Create a new account with secure credential storage.
        
        Args:
            account_data: Dictionary containing account information
        
        Returns:
            Account: Created account instance, or None if creation failed
        """
        try:
            # Extract and validate required fields
            required_fields = ["name", "email_address"]
            for field in required_fields:
                if field not in account_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Create account instance
            account = Account(
                name=account_data["name"],
                email_address=account_data["email_address"],
                account_type=account_data.get("account_type", AccountType.EMAIL),
                display_name=account_data.get("display_name"),
                email_protocol=account_data.get("email_protocol"),
                incoming_server=account_data.get("incoming_server"),
                incoming_port=account_data.get("incoming_port"),
                incoming_security=account_data.get("incoming_security"),
                incoming_username=account_data.get("incoming_username"),
                outgoing_server=account_data.get("outgoing_server"),
                outgoing_port=account_data.get("outgoing_port"),
                outgoing_security=account_data.get("outgoing_security"),
                outgoing_username=account_data.get("outgoing_username"),
                outgoing_auth_required=account_data.get("outgoing_auth_required", True),
                caldav_server=account_data.get("caldav_server"),
                caldav_username=account_data.get("caldav_username"),
                caldav_sync_enabled=account_data.get("caldav_sync_enabled", False),
                carddav_server=account_data.get("carddav_server"),
                carddav_username=account_data.get("carddav_username"),
                carddav_sync_enabled=account_data.get("carddav_sync_enabled", False),
                auth_method=account_data.get("auth_method"),
                sync_frequency=account_data.get("sync_frequency", 15),
                keep_messages_days=account_data.get("keep_messages_days", 30),
                advanced_settings=account_data.get("advanced_settings"),
                provider_id=account_data.get("provider_id")
            )
            
            # Add to session and flush to get ID
            self.session.add(account)
            self.session.flush()
            
            # Store credentials securely
            self._store_account_credentials(account, account_data)
            
            # Commit the transaction
            self.session.commit()
            
            self.logger.info(f"Created account: {account.name} ({account.email_address})")
            return account
            
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to create account: {e}")
            return None
    
    def _store_account_credentials(self, account: Account, account_data: Dict[str, Any]) -> None:
        """Store account credentials securely."""
        try:
            # Store incoming mail password
            if "incoming_password" in account_data:
                key = self.credential_manager.store_password(
                    account.id, "incoming", account_data["incoming_password"]
                )
                account.incoming_password_key = key
            
            # Store outgoing mail password
            if "outgoing_password" in account_data:
                key = self.credential_manager.store_password(
                    account.id, "outgoing", account_data["outgoing_password"]
                )
                account.outgoing_password_key = key
            
            # Store CalDAV password
            if "caldav_password" in account_data:
                key = self.credential_manager.store_password(
                    account.id, "caldav", account_data["caldav_password"]
                )
                account.caldav_password_key = key
            
            # Store CardDAV password
            if "carddav_password" in account_data:
                key = self.credential_manager.store_password(
                    account.id, "carddav", account_data["carddav_password"]
                )
                account.carddav_password_key = key
            
            # Store OAuth tokens
            if "oauth_tokens" in account_data:
                key = self.credential_manager.store_oauth_tokens(
                    account.id, account_data["oauth_tokens"]
                )
                account.oauth2_token_key = key
                
        except CredentialStorageError as e:
            self.logger.error(f"Failed to store credentials for account {account.id}: {e}")
            raise
    
    def get_account(self, account_id: int) -> Optional[Account]:
        """
        Get an account by ID.
        
        Args:
            account_id: Account ID
        
        Returns:
            Account: Account instance, or None if not found
        """
        try:
            return self.session.query(Account).filter(Account.id == account_id).first()
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get account {account_id}: {e}")
            return None
    
    def get_account_by_email(self, email_address: str) -> Optional[Account]:
        """
        Get an account by email address.
        
        Args:
            email_address: Email address
        
        Returns:
            Account: Account instance, or None if not found
        """
        try:
            return self.session.query(Account).filter(
                Account.email_address == email_address
            ).first()
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get account by email {email_address}: {e}")
            return None
    
    def get_all_accounts(self, enabled_only: bool = False) -> List[Account]:
        """
        Get all accounts.
        
        Args:
            enabled_only: If True, return only enabled accounts
        
        Returns:
            List[Account]: List of account instances
        """
        try:
            query = self.session.query(Account)
            
            if enabled_only:
                query = query.filter(Account.is_enabled == True)
            
            return query.order_by(Account.name).all()
            
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get accounts: {e}")
            return []
    
    def get_accounts_by_type(self, account_type: AccountType) -> List[Account]:
        """
        Get accounts by type.
        
        Args:
            account_type: Account type to filter by
        
        Returns:
            List[Account]: List of matching accounts
        """
        try:
            return self.session.query(Account).filter(
                Account.account_type == account_type,
                Account.is_enabled == True
            ).order_by(Account.name).all()
            
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get accounts by type {account_type}: {e}")
            return []
    
    def get_default_account(self) -> Optional[Account]:
        """
        Get the default account.
        
        Returns:
            Account: Default account, or None if not set
        """
        try:
            return self.session.query(Account).filter(
                Account.is_default == True,
                Account.is_enabled == True
            ).first()
            
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get default account: {e}")
            return None
    
    def set_default_account(self, account_id: int) -> bool:
        """
        Set an account as the default.
        
        Args:
            account_id: ID of account to set as default
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Clear existing default
            self.session.query(Account).filter(
                Account.is_default == True
            ).update({"is_default": False})
            
            # Set new default
            account = self.get_account(account_id)
            if account:
                account.is_default = True
                self.session.commit()
                self.logger.info(f"Set default account: {account.name}")
                return True
            
            return False
            
        except SQLAlchemyError as e:
            self.session.rollback()
            self.logger.error(f"Failed to set default account {account_id}: {e}")
            return False
    
    def update_account(self, account_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update an account.
        
        Args:
            account_id: Account ID
            updates: Dictionary of fields to update
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            account = self.get_account(account_id)
            if not account:
                return False
            
            # Update account fields
            for field, value in updates.items():
                if hasattr(account, field) and field not in [
                    "id", "created_at", "updated_at"
                ]:
                    setattr(account, field, value)
            
            # Handle credential updates
            self._update_account_credentials(account, updates)
            
            self.session.commit()
            self.logger.info(f"Updated account: {account.name}")
            return True
            
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to update account {account_id}: {e}")
            return False
    
    def _update_account_credentials(self, account: Account, updates: Dict[str, Any]) -> None:
        """Update account credentials."""
        credential_fields = {
            "incoming_password": "incoming_password_key",
            "outgoing_password": "outgoing_password_key",
            "caldav_password": "caldav_password_key",
            "carddav_password": "carddav_password_key"
        }
        
        for password_field, key_field in credential_fields.items():
            if password_field in updates:
                current_key = getattr(account, key_field)
                new_password = updates[password_field]
                
                if current_key:
                    # Update existing credential
                    success = self.credential_manager.update_password(current_key, new_password)
                    if not success:
                        self.logger.warning(f"Failed to update {password_field} for account {account.id}")
                else:
                    # Store new credential
                    password_type = password_field.replace("_password", "")
                    key = self.credential_manager.store_password(
                        account.id, password_type, new_password
                    )
                    setattr(account, key_field, key)
        
        # Handle OAuth token updates
        if "oauth_tokens" in updates:
            current_key = account.oauth2_token_key
            new_tokens = updates["oauth_tokens"]
            
            if current_key:
                # Update existing tokens
                try:
                    # Delete old tokens and store new ones
                    self.credential_manager.delete_password(current_key)
                    key = self.credential_manager.store_oauth_tokens(account.id, new_tokens)
                    account.oauth2_token_key = key
                except CredentialStorageError as e:
                    self.logger.error(f"Failed to update OAuth tokens for account {account.id}: {e}")
            else:
                # Store new tokens
                key = self.credential_manager.store_oauth_tokens(account.id, new_tokens)
                account.oauth2_token_key = key
    
    def delete_account(self, account_id: int) -> bool:
        """
        Delete an account and its credentials.
        
        Args:
            account_id: Account ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            account = self.get_account(account_id)
            if not account:
                return False
            
            # Delete stored credentials
            self._delete_account_credentials(account)
            
            # Delete connection test results
            self.session.query(AccountConnectionTest).filter(
                AccountConnectionTest.account_id == account_id
            ).delete()
            
            # Delete the account
            self.session.delete(account)
            self.session.commit()
            
            self.logger.info(f"Deleted account: {account.name} ({account.email_address})")
            return True
            
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to delete account {account_id}: {e}")
            return False
    
    def _delete_account_credentials(self, account: Account) -> None:
        """Delete all credentials for an account."""
        credential_keys = [
            account.incoming_password_key,
            account.outgoing_password_key,
            account.caldav_password_key,
            account.carddav_password_key,
            account.oauth2_token_key
        ]
        
        for key in credential_keys:
            if key:
                try:
                    self.credential_manager.delete_password(key)
                except Exception as e:
                    self.logger.warning(f"Failed to delete credential {key}: {e}")
    
    def get_account_credentials(self, account: Account, credential_type: str) -> Optional[str]:
        """
        Get stored credentials for an account.
        
        Args:
            account: Account instance
            credential_type: Type of credential (incoming, outgoing, caldav, carddav)
        
        Returns:
            str: The credential, or None if not found
        """
        try:
            key_field = f"{credential_type}_password_key"
            credential_key = getattr(account, key_field, None)
            
            if credential_key:
                return self.credential_manager.retrieve_password(credential_key)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get {credential_type} credentials for account {account.id}: {e}")
            return None
    
    def get_account_oauth_tokens(self, account: Account) -> Optional[Dict[str, Any]]:
        """
        Get OAuth tokens for an account.
        
        Args:
            account: Account instance
        
        Returns:
            Dict: OAuth tokens, or None if not found
        """
        try:
            if account.oauth2_token_key:
                return self.credential_manager.retrieve_oauth_tokens(account.oauth2_token_key)
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get OAuth tokens for account {account.id}: {e}")
            return None
    
    def record_connection_test(self, account_id: int, test_type: str, 
                             success: bool, error_message: Optional[str] = None,
                             response_time_ms: Optional[int] = None) -> bool:
        """
        Record a connection test result.
        
        Args:
            account_id: Account ID
            test_type: Type of test (incoming, outgoing, caldav, carddav)
            success: Whether the test succeeded
            error_message: Error message if test failed
            response_time_ms: Response time in milliseconds
        
        Returns:
            bool: True if recorded successfully, False otherwise
        """
        try:
            test_result = AccountConnectionTest(
                account_id=account_id,
                test_type=test_type,
                test_result="success" if success else "failure",
                error_message=error_message,
                response_time_ms=response_time_ms
            )
            
            self.session.add(test_result)
            self.session.commit()
            
            # Update account connection status
            account = self.get_account(account_id)
            if account:
                if success:
                    account.connection_status = "connected"
                    account.last_error = None
                else:
                    account.connection_status = "error"
                    account.last_error = error_message
                self.session.commit()
            
            return True
            
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to record connection test: {e}")
            return False
    
    def get_connection_test_history(self, account_id: int, 
                                  test_type: Optional[str] = None,
                                  limit: int = 10) -> List[AccountConnectionTest]:
        """
        Get connection test history for an account.
        
        Args:
            account_id: Account ID
            test_type: Optional test type filter
            limit: Maximum number of results
        
        Returns:
            List[AccountConnectionTest]: List of test results
        """
        try:
            query = self.session.query(AccountConnectionTest).filter(
                AccountConnectionTest.account_id == account_id
            )
            
            if test_type:
                query = query.filter(AccountConnectionTest.test_type == test_type)
            
            return query.order_by(desc(AccountConnectionTest.tested_at)).limit(limit).all()
            
        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get connection test history: {e}")
            return [] 