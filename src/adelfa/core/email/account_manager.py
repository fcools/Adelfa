"""
Account manager for Adelfa PIM suite.

Provides high-level account management functionality integrating
the setup wizard, repository, and credential management.
"""

from typing import List, Optional, Dict, Any, Tuple
from PyQt6.QtWidgets import QWidget, QMessageBox
from sqlalchemy.orm import Session

from ...utils.logging_setup import get_logger
from ...data.repositories.account_repository import AccountRepository
from ...data.models.accounts import Account, AccountType, EmailProtocol, SecurityType, AuthMethod
from ...gui.email.account_setup_wizard import AccountSetupWizard
from .protocol_detector import ProtocolDetector, DetectionResult
from .credential_manager import get_credential_manager

logger = get_logger(__name__)


class AccountManager:
    """
    High-level account management.
    
    Provides a unified interface for account creation, management,
    and integration with the GUI components.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the account manager.
        
        Args:
            session: SQLAlchemy session instance
        """
        self.session = session
        self.repository = AccountRepository(session)
        self.credential_manager = get_credential_manager()
        self.protocol_detector = ProtocolDetector()
        self.logger = logger
    
    def show_account_setup_wizard(self, parent: Optional[QWidget] = None) -> Optional[Account]:
        """
        Show the account setup wizard and create account if completed.
        
        Args:
            parent: Parent widget for the wizard
        
        Returns:
            Account: Created account if wizard completed successfully, None otherwise
        """
        try:
            wizard = AccountSetupWizard(parent)
            
            if wizard.exec() == AccountSetupWizard.DialogCode.Accepted:
                # Extract account data from wizard
                account_data = self._extract_wizard_data(wizard)
                
                # Create the account
                account = self.repository.create_account(account_data)
                
                if account:
                    self.logger.info(f"Account created successfully: {account.name}")
                    
                    # Show success message
                    QMessageBox.information(
                        parent,
                        "Account Created",
                        f"Account '{account.name}' has been created successfully!"
                    )
                    
                    return account
                else:
                    # Show error message
                    QMessageBox.critical(
                        parent,
                        "Account Creation Failed",
                        "Failed to create the account. Please check the logs for details."
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to show account setup wizard: {e}")
            
            QMessageBox.critical(
                parent,
                "Setup Error",
                f"An error occurred during account setup: {str(e)}"
            )
            
            return None
    
    def _extract_wizard_data(self, wizard: AccountSetupWizard) -> Dict[str, Any]:
        """Extract account data from the completed wizard."""
        account_data = {}
        
        # Basic account information
        account_data["name"] = wizard.field("account_name")
        account_data["email_address"] = wizard.field("email_address")
        account_data["display_name"] = wizard.field("display_name")
        account_data["account_type"] = AccountType.COMBINED  # Supports email, calendar, contacts
        
        # Credentials
        username = wizard.field("username")
        password = wizard.field("password")
        save_password = wizard.field("save_password")
        
        account_data["incoming_username"] = username
        account_data["outgoing_username"] = username
        
        if save_password:
            account_data["incoming_password"] = password
            account_data["outgoing_password"] = password
        
        # Email settings
        detection_result = wizard.field("detection_result")
        if detection_result and detection_result.email_settings:
            # Use auto-detected settings
            self._apply_detected_email_settings(account_data, detection_result)
        else:
            # Use manual settings
            self._apply_manual_email_settings(account_data, wizard)
        
        # Calendar settings
        if wizard.field("enable_calendar"):
            account_data["caldav_server"] = wizard.field("calendar_server")
            account_data["caldav_username"] = wizard.field("calendar_username") or username
            account_data["caldav_sync_enabled"] = True
            
            if save_password:
                # Use same password as email or specific calendar password
                calendar_password = wizard.field("calendar_password")
                account_data["caldav_password"] = calendar_password or password
        
        # Contacts settings
        if wizard.field("enable_contacts"):
            account_data["carddav_server"] = wizard.field("contacts_server")
            account_data["carddav_username"] = wizard.field("contacts_username") or username
            account_data["carddav_sync_enabled"] = True
            
            if save_password:
                # Use same password as email or specific contacts password
                contacts_password = wizard.field("contacts_password")
                account_data["carddav_password"] = contacts_password or password
        
        return account_data
    
    def _apply_detected_email_settings(self, account_data: Dict[str, Any], 
                                     detection_result: DetectionResult) -> None:
        """Apply auto-detected email settings."""
        email_settings = detection_result.email_settings
        
        # IMAP settings
        if "imap" in email_settings:
            imap = email_settings["imap"]
            account_data["email_protocol"] = EmailProtocol.IMAP
            account_data["incoming_server"] = imap.server
            account_data["incoming_port"] = imap.port
            account_data["incoming_security"] = imap.security
        
        # SMTP settings
        if "smtp" in email_settings:
            smtp = email_settings["smtp"]
            account_data["outgoing_server"] = smtp.server
            account_data["outgoing_port"] = smtp.port
            account_data["outgoing_security"] = smtp.security
            account_data["outgoing_auth_required"] = True
        
        # Authentication method
        if detection_result.provider_name:
            # For known providers, we might need OAuth2
            if detection_result.provider_name in ["Gmail", "Outlook.com", "Hotmail"]:
                account_data["auth_method"] = AuthMethod.OAUTH2
            else:
                account_data["auth_method"] = AuthMethod.PASSWORD
    
    def _apply_manual_email_settings(self, account_data: Dict[str, Any], 
                                   wizard: AccountSetupWizard) -> None:
        """Apply manually configured email settings."""
        # This would be populated from the ServerSettingsPage
        # For now, we'll use some defaults since manual setup needs more wizard pages
        account_data["email_protocol"] = EmailProtocol.IMAP
        account_data["incoming_server"] = wizard.field("incoming_server") or ""
        account_data["incoming_port"] = wizard.field("incoming_port") or 993
        account_data["incoming_security"] = SecurityType.TLS_SSL
        account_data["outgoing_server"] = wizard.field("outgoing_server") or ""
        account_data["outgoing_port"] = wizard.field("outgoing_port") or 587
        account_data["outgoing_security"] = SecurityType.STARTTLS
        account_data["outgoing_auth_required"] = True
        account_data["auth_method"] = AuthMethod.PASSWORD
    
    def get_all_accounts(self, enabled_only: bool = True) -> List[Account]:
        """
        Get all configured accounts.
        
        Args:
            enabled_only: If True, return only enabled accounts
        
        Returns:
            List[Account]: List of accounts
        """
        return self.repository.get_all_accounts(enabled_only)
    
    def get_default_account(self) -> Optional[Account]:
        """
        Get the default account.
        
        Returns:
            Account: Default account, or None if not set
        """
        return self.repository.get_default_account()
    
    def set_default_account(self, account_id: int) -> bool:
        """
        Set an account as the default.
        
        Args:
            account_id: Account ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        return self.repository.set_default_account(account_id)
    
    def delete_account(self, account_id: int, parent: Optional[QWidget] = None) -> bool:
        """
        Delete an account with confirmation.
        
        Args:
            account_id: Account ID
            parent: Parent widget for confirmation dialog
        
        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            account = self.repository.get_account(account_id)
            if not account:
                return False
            
            # Show confirmation dialog
            reply = QMessageBox.question(
                parent,
                "Delete Account",
                f"Are you sure you want to delete the account '{account.name}'?\n\n"
                "This will remove all stored credentials and cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                success = self.repository.delete_account(account_id)
                
                if success:
                    QMessageBox.information(
                        parent,
                        "Account Deleted",
                        f"Account '{account.name}' has been deleted successfully."
                    )
                else:
                    QMessageBox.critical(
                        parent,
                        "Deletion Failed",
                        f"Failed to delete account '{account.name}'. Please check the logs."
                    )
                
                return success
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to delete account {account_id}: {e}")
            
            QMessageBox.critical(
                parent,
                "Deletion Error",
                f"An error occurred while deleting the account: {str(e)}"
            )
            
            return False
    
    def test_account_connection(self, account: Account, 
                              test_type: str = "incoming") -> Tuple[bool, Optional[str]]:
        """
        Test connection for an account.
        
        Args:
            account: Account to test
            test_type: Type of connection to test (incoming, outgoing, caldav, carddav)
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if test_type == "incoming":
                return self._test_incoming_connection(account)
            elif test_type == "outgoing":
                return self._test_outgoing_connection(account)
            elif test_type == "caldav":
                return self._test_caldav_connection(account)
            elif test_type == "carddav":
                return self._test_carddav_connection(account)
            else:
                return False, f"Unknown test type: {test_type}"
                
        except Exception as e:
            self.logger.error(f"Connection test failed for account {account.id}: {e}")
            return False, str(e)
    
    def _test_incoming_connection(self, account: Account) -> Tuple[bool, Optional[str]]:
        """Test incoming email connection."""
        if not account.incoming_server:
            return False, "No incoming server configured"
        
        password = self.repository.get_account_credentials(account, "incoming")
        if not password:
            return False, "No incoming password stored"
        
        from .protocol_detector import ServerSettings
        
        settings = ServerSettings(
            server=account.incoming_server,
            port=account.incoming_port,
            security=account.incoming_security,
            protocol=account.email_protocol
        )
        
        success, error = self.protocol_detector.test_connection(
            settings, account.incoming_username, password
        )
        
        # Record test result
        self.repository.record_connection_test(
            account.id, "incoming", success, error
        )
        
        return success, error
    
    def _test_outgoing_connection(self, account: Account) -> Tuple[bool, Optional[str]]:
        """Test outgoing email connection."""
        if not account.outgoing_server:
            return False, "No outgoing server configured"
        
        password = self.repository.get_account_credentials(account, "outgoing")
        if not password:
            return False, "No outgoing password stored"
        
        from .protocol_detector import ServerSettings
        
        settings = ServerSettings(
            server=account.outgoing_server,
            port=account.outgoing_port,
            security=account.outgoing_security
        )
        
        success, error = self.protocol_detector.test_connection(
            settings, account.outgoing_username, password
        )
        
        # Record test result
        self.repository.record_connection_test(
            account.id, "outgoing", success, error
        )
        
        return success, error
    
    def _test_caldav_connection(self, account: Account) -> Tuple[bool, Optional[str]]:
        """Test CalDAV connection."""
        if not account.caldav_server:
            return False, "No CalDAV server configured"
        
        password = self.repository.get_account_credentials(account, "caldav")
        if not password:
            return False, "No CalDAV password stored"
        
        success, error = self.protocol_detector.test_caldav_connection(
            account.caldav_server, account.caldav_username, password
        )
        
        # Record test result
        self.repository.record_connection_test(
            account.id, "caldav", success, error
        )
        
        return success, error
    
    def _test_carddav_connection(self, account: Account) -> Tuple[bool, Optional[str]]:
        """Test CardDAV connection."""
        if not account.carddav_server:
            return False, "No CardDAV server configured"
        
        password = self.repository.get_account_credentials(account, "carddav")
        if not password:
            return False, "No CardDAV password stored"
        
        success, error = self.protocol_detector.test_carddav_connection(
            account.carddav_server, account.carddav_username, password
        )
        
        # Record test result
        self.repository.record_connection_test(
            account.id, "carddav", success, error
        )
        
        return success, error
    
    def get_account_summary(self, account: Account) -> Dict[str, Any]:
        """
        Get a summary of account configuration and status.
        
        Args:
            account: Account to summarize
        
        Returns:
            Dict: Account summary information
        """
        summary = {
            "id": account.id,
            "name": account.name,
            "email_address": account.email_address,
            "display_name": account.display_name,
            "account_type": account.account_type.value,
            "is_enabled": account.is_enabled,
            "is_default": account.is_default,
            "connection_status": account.connection_status,
            "last_error": account.last_error,
            "last_sync": account.last_sync.isoformat() if account.last_sync else None,
            "features": {
                "email": bool(account.incoming_server and account.outgoing_server),
                "calendar": account.caldav_sync_enabled,
                "contacts": account.carddav_sync_enabled
            },
            "servers": {
                "incoming": f"{account.incoming_server}:{account.incoming_port}" if account.incoming_server else None,
                "outgoing": f"{account.outgoing_server}:{account.outgoing_port}" if account.outgoing_server else None,
                "caldav": account.caldav_server,
                "carddav": account.carddav_server
            }
        }
        
        return summary 