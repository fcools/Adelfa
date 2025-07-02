"""
Email manager for Adelfa PIM suite.

Provides a unified interface for email operations, coordinating IMAP, SMTP,
and account management functionality with local caching for fast startup.
"""

import threading
from typing import List, Optional, Dict, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy.orm import Session

from ...utils.logging_setup import get_logger
from ...data.models.accounts import Account, EmailProtocol
from ..cache_manager import CacheManager
from .credential_manager import CredentialManager
from .imap_client import IMAPClient, EmailMessage, FolderInfo, IMAPClientError
from .smtp_client import SMTPClient, OutgoingEmail, EmailAddress, SMTPClientError

logger = get_logger(__name__)


@dataclass
class EmailAccount:
    """Email account with active clients."""
    account: Account
    imap_client: Optional[IMAPClient] = None
    smtp_client: Optional[SMTPClient] = None
    is_connected: bool = False
    last_sync: Optional[datetime] = None
    error_count: int = 0
    max_errors: int = 5


class EmailManagerError(Exception):
    """Email manager specific error."""
    pass


class EmailManager:
    """
    Unified email manager.
    
    Manages multiple email accounts, provides unified access to IMAP/SMTP
    functionality, and handles synchronization and notifications.
    """
    
    def __init__(self, credential_manager: CredentialManager, db_session: Session):
        """
        Initialize email manager.
        
        Args:
            credential_manager: Credential manager for password retrieval
            db_session: Database session for caching
        """
        self.credential_manager = credential_manager
        self.cache_manager = CacheManager(db_session)
        self.accounts: Dict[int, EmailAccount] = {}
        self.default_account_id: Optional[int] = None
        self.message_callbacks: List[Callable[[str, EmailMessage], None]] = []
        self.folder_callbacks: List[Callable[[str, FolderInfo], None]] = []
        self.logger = logger
        self._lock = threading.Lock()
        
        # Cache settings
        self.cache_max_age_folders = timedelta(hours=1)  # Refresh folders every hour
        self.cache_max_age_messages = timedelta(hours=4)  # Refresh messages every 4 hours
    
    def add_account(self, account: Account) -> bool:
        """
        Add an email account to the manager.
        
        Args:
            account: Email account to add
        
        Returns:
            bool: True if added successfully
        """
        try:
            with self._lock:
                if account.id in self.accounts:
                    self.logger.warning(f"Account {account.id} already exists")
                    return False
                
                email_account = EmailAccount(account=account)
                
                # Create IMAP client if IMAP protocol
                if account.email_protocol == EmailProtocol.IMAP:
                    email_account.imap_client = IMAPClient(account, self.credential_manager)
                
                # Create SMTP client
                email_account.smtp_client = SMTPClient(account, self.credential_manager)
                
                self.accounts[account.id] = email_account
                
                # Set as default if first account
                if not self.default_account_id:
                    self.default_account_id = account.id
                
                self.logger.info(f"Added email account: {account.name}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to add account: {e}")
            return False
    
    def remove_account(self, account_id: int) -> bool:
        """
        Remove an email account from the manager.
        
        Args:
            account_id: Account ID to remove
        
        Returns:
            bool: True if removed successfully
        """
        try:
            with self._lock:
                if account_id not in self.accounts:
                    return False
                
                email_account = self.accounts[account_id]
                
                # Disconnect clients
                if email_account.imap_client:
                    email_account.imap_client.disconnect()
                
                if email_account.smtp_client:
                    email_account.smtp_client.disconnect()
                
                del self.accounts[account_id]
                
                # Update default account if needed
                if self.default_account_id == account_id:
                    self.default_account_id = next(iter(self.accounts.keys()), None)
                
                self.logger.info(f"Removed email account: {account_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to remove account: {e}")
            return False
    
    def connect_account(self, account_id: int) -> bool:
        """
        Connect to an email account's servers.
        
        Args:
            account_id: Account ID to connect
        
        Returns:
            bool: True if connected successfully
        """
        try:
            if account_id not in self.accounts:
                raise EmailManagerError(f"Account {account_id} not found")
            
            email_account = self.accounts[account_id]
            
            # Connect IMAP client
            imap_connected = True
            if email_account.imap_client:
                imap_connected = email_account.imap_client.connect()
                # Note: IDLE monitoring disabled temporarily to avoid connection conflicts
            
            # Connect SMTP client
            smtp_connected = True
            if email_account.smtp_client:
                smtp_connected = email_account.smtp_client.connect()
            
            email_account.is_connected = imap_connected and smtp_connected
            email_account.error_count = 0
            
            if email_account.is_connected:
                email_account.last_sync = datetime.now(timezone.utc)
                self.logger.info(f"Connected account {account_id}")
            
            return email_account.is_connected
            
        except Exception as e:
            self.logger.error(f"Failed to connect account {account_id}: {e}")
            if account_id in self.accounts:
                self.accounts[account_id].error_count += 1
            return False
    
    def disconnect_account(self, account_id: int):
        """
        Disconnect from an email account's servers.
        
        Args:
            account_id: Account ID to disconnect
        """
        try:
            if account_id not in self.accounts:
                return
            
            email_account = self.accounts[account_id]
            
            if email_account.imap_client:
                email_account.imap_client.disconnect()
            
            if email_account.smtp_client:
                email_account.smtp_client.disconnect()
            
            email_account.is_connected = False
            
            self.logger.info(f"Disconnected account {account_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to disconnect account {account_id}: {e}")
    
    def connect_all_accounts(self):
        """Connect to all configured accounts."""
        for account_id in list(self.accounts.keys()):
            self.connect_account(account_id)
    
    def disconnect_all_accounts(self):
        """Disconnect from all accounts."""
        for account_id in list(self.accounts.keys()):
            self.disconnect_account(account_id)
    
    def get_folders(self, account_id: Optional[int] = None, use_cache: bool = True) -> List[FolderInfo]:
        """
        Get folder list for an account with caching support.
        
        Args:
            account_id: Account ID (uses default if None)
            use_cache: Whether to use cached data for immediate response
        
        Returns:
            List[FolderInfo]: List of folders
        """
        try:
            account_id = account_id or self.default_account_id
            if not account_id:
                return []
            
            # Try cache first if enabled
            if use_cache:
                cached_folders = self.cache_manager.get_cached_folders(account_id)
                cache_age = self.cache_manager.folders_cache_age(account_id)
                
                # Return cached data if available and not too old
                if cached_folders and (cache_age is None or cache_age < self.cache_max_age_folders):
                    self.logger.debug(f"Using cached folders for account {account_id}")
                    return cached_folders
                
                # If cache is stale or empty, start background refresh but return cache for now
                if cached_folders:
                    self.logger.debug(f"Cache stale, refreshing in background for account {account_id}")
                    threading.Thread(
                        target=self._refresh_folders_background,
                        args=(account_id,),
                        daemon=True
                    ).start()
                    return cached_folders
            
            # No cache or cache disabled - fetch from server
            if account_id not in self.accounts:
                return []
            
            email_account = self.accounts[account_id]
            if not email_account.imap_client:
                return []
            
            folders = email_account.imap_client.get_folders()
            
            # Update cache with fresh data
            if folders:
                self.cache_manager.cache_folders(account_id, folders)
            
            # Notify callbacks
            for callback in self.folder_callbacks:
                for folder in folders:
                    callback(email_account.account.name, folder)
            
            return folders
            
        except Exception as e:
            self.logger.error(f"Failed to get folders: {e}")
            # Fallback to cache if server fetch fails
            if use_cache:
                return self.cache_manager.get_cached_folders(account_id)
            return []
    
    def search_messages(self, criteria: str = 'ALL', folder: str = 'INBOX', 
                       account_id: Optional[int] = None) -> List[int]:
        """
        Search for messages.
        
        Args:
            criteria: IMAP search criteria
            folder: Folder to search in
            account_id: Account ID, or None for default account
        
        Returns:
            List[int]: Message UIDs matching criteria
        """
        account_id = account_id or self.default_account_id
        if not account_id or account_id not in self.accounts:
            return []
        
        email_account = self.accounts[account_id]
        if not email_account.imap_client:
            return []
        
        try:
            email_account.imap_client.select_folder(folder)
            return email_account.imap_client.search_messages(criteria)
        except Exception as e:
            self.logger.error(f"Failed to search messages: {e}")
            return []
    
    def get_message(self, uid: int, folder: str = 'INBOX', include_body: bool = True,
                   account_id: Optional[int] = None) -> Optional[EmailMessage]:
        """
        Get a specific message.
        
        Args:
            uid: Message UID
            folder: Folder containing the message
            include_body: Whether to include message body
            account_id: Account ID, or None for default account
        
        Returns:
            EmailMessage: Message or None if not found
        """
        account_id = account_id or self.default_account_id
        if not account_id or account_id not in self.accounts:
            return None
        
        email_account = self.accounts[account_id]
        if not email_account.imap_client:
            return None
        
        try:
            email_account.imap_client.select_folder(folder)
            return email_account.imap_client.get_message(uid, include_body)
        except Exception as e:
            self.logger.error(f"Failed to get message {uid}: {e}")
            return None
    
    def get_recent_messages(self, folder: str = 'INBOX', limit: int = 50,
                           account_id: Optional[int] = None, use_cache: bool = True) -> List[EmailMessage]:
        """
        Get recent messages from a folder with caching support.
        
        Args:
            folder: Folder to get messages from
            limit: Maximum number of messages to retrieve
            account_id: Account ID, or None for default account
            use_cache: Whether to use cached data for immediate response
        
        Returns:
            List[EmailMessage]: Recent messages
        """
        try:
            account_id = account_id or self.default_account_id
            if not account_id:
                return []
            
            # Try cache first if enabled
            if use_cache:
                cached_messages = self.cache_manager.get_cached_messages(account_id, folder, limit)
                cache_age = self.cache_manager.messages_cache_age(account_id, folder)
                
                # Return cached data if available and not too old
                if cached_messages and (cache_age is None or cache_age < self.cache_max_age_messages):
                    self.logger.debug(f"Using cached messages for {folder} in account {account_id}")
                    return cached_messages
                
                # If cache is stale or empty, start background refresh but return cache for now
                if cached_messages:
                    self.logger.debug(f"Message cache stale, refreshing in background for {folder}")
                    threading.Thread(
                        target=self._refresh_messages_background,
                        args=(account_id, folder, limit),
                        daemon=True
                    ).start()
                    return cached_messages
            
            # No cache or cache disabled - fetch from server
            if account_id not in self.accounts:
                return []
            
            email_account = self.accounts[account_id]
            if not email_account.imap_client:
                return []
            
            # Get recent message UIDs
            uids = self.search_messages('ALL', folder, account_id)
            
            # Sort by UID (most recent first) and limit
            uids = sorted(uids, reverse=True)[:limit]
            
            # Retrieve messages
            messages = []
            for uid in uids:
                message = self.get_message(uid, folder, include_body=False, account_id=account_id)
                if message:
                    messages.append(message)
            
            # Update cache with fresh data
            if messages:
                self.cache_manager.cache_messages(account_id, folder, messages)
            
            return messages
            
        except Exception as e:
            self.logger.error(f"Failed to get recent messages: {e}")
            # Fallback to cache if server fetch fails (even if stale)
            if use_cache:
                cached_messages = self.cache_manager.get_cached_messages(account_id, folder, limit)
                if cached_messages:
                    self.logger.info(f"Using stale cached messages as fallback for {folder}")
                    return cached_messages
            return []
    
    def send_email(self, email: OutgoingEmail, account_id: Optional[int] = None) -> bool:
        """
        Send an email message.
        
        Args:
            email: Email message to send
            account_id: Account ID, or None for default account
        
        Returns:
            bool: True if sent successfully
        """
        account_id = account_id or self.default_account_id
        if not account_id or account_id not in self.accounts:
            raise EmailManagerError("No account available for sending")
        
        email_account = self.accounts[account_id]
        if not email_account.smtp_client:
            raise EmailManagerError("No SMTP client available")
        
        try:
            return email_account.smtp_client.send_email(email)
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            raise EmailManagerError(f"Failed to send email: {e}")
    
    def mark_as_read(self, uid: int, folder: str = 'INBOX', account_id: Optional[int] = None):
        """Mark message as read."""
        account_id = account_id or self.default_account_id
        if not account_id or account_id not in self.accounts:
            return
        
        email_account = self.accounts[account_id]
        if not email_account.imap_client:
            return
        
        try:
            email_account.imap_client.select_folder(folder)
            email_account.imap_client.mark_as_read(uid)
        except Exception as e:
            self.logger.error(f"Failed to mark message as read: {e}")
    
    def mark_as_unread(self, uid: int, folder: str = 'INBOX', account_id: Optional[int] = None):
        """Mark message as unread."""
        account_id = account_id or self.default_account_id
        if not account_id or account_id not in self.accounts:
            return
        
        email_account = self.accounts[account_id]
        if not email_account.imap_client:
            return
        
        try:
            email_account.imap_client.select_folder(folder)
            email_account.imap_client.mark_as_unread(uid)
        except Exception as e:
            self.logger.error(f"Failed to mark message as unread: {e}")
    
    def delete_message(self, uid: int, folder: str = 'INBOX', permanent: bool = False,
                      account_id: Optional[int] = None):
        """
        Delete a message.
        
        Args:
            uid: Message UID
            folder: Folder containing the message
            permanent: Whether to permanently delete (expunge)
            account_id: Account ID, or None for default account
        """
        account_id = account_id or self.default_account_id
        if not account_id or account_id not in self.accounts:
            return
        
        email_account = self.accounts[account_id]
        if not email_account.imap_client:
            return
        
        try:
            email_account.imap_client.select_folder(folder)
            email_account.imap_client.delete_message(uid, expunge=permanent)
        except Exception as e:
            self.logger.error(f"Failed to delete message: {e}")
    
    def add_message_callback(self, callback: Callable[[str, EmailMessage], None]):
        """
        Add callback for message events.
        
        Args:
            callback: Function called with (event_type, message)
        """
        self.message_callbacks.append(callback)
    
    def add_folder_callback(self, callback: Callable[[str, FolderInfo], None]):
        """
        Add callback for folder events.
        
        Args:
            callback: Function called with (event_type, folder_info)
        """
        self.folder_callbacks.append(callback)
    
    def get_account_status(self, account_id: int) -> Dict[str, Any]:
        """
        Get account connection status.
        
        Args:
            account_id: Account ID
        
        Returns:
            Dict with status information
        """
        if account_id not in self.accounts:
            return {'connected': False, 'error': 'Account not found'}
        
        email_account = self.accounts[account_id]
        
        return {
            'connected': email_account.is_connected,
            'last_sync': email_account.last_sync,
            'error_count': email_account.error_count,
            'account_name': email_account.account.name,
            'email_address': email_account.account.email_address
        }
    
    def _handle_imap_notification(self, account_id: int, event_type: str, uids: List[int]):
        """Handle IMAP IDLE notifications."""
        try:
            if event_type == 'new_message':
                # Notify callbacks about new messages
                for callback in self.message_callbacks:
                    try:
                        # Note: We'd need to fetch the actual message here
                        # For now, just pass the event type
                        callback(event_type, None)
                    except Exception as e:
                        self.logger.error(f"Message callback error: {e}")
            
            self.logger.debug(f"IMAP notification: {event_type} for account {account_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to handle IMAP notification: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect_all_accounts()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect_all_accounts()
    
    def _refresh_folders_background(self, account_id: int):
        """
        Background method to refresh folder cache.
        
        Args:
            account_id: Account ID to refresh
        """
        try:
            self.logger.debug(f"Background refresh of folders for account {account_id}")
            # Fetch folders without using cache
            folders = self.get_folders(account_id, use_cache=False)
            self.logger.debug(f"Background refresh completed: {len(folders)} folders")
        except Exception as e:
            self.logger.error(f"Background folder refresh failed: {e}")
    
    def _refresh_messages_background(self, account_id: int, folder: str, limit: int):
        """
        Background method to refresh message cache.
        
        Args:
            account_id: Account ID to refresh
            folder: Folder to refresh
            limit: Number of messages to fetch
        """
        try:
            self.logger.debug(f"Background refresh of messages for {folder} in account {account_id}")
            # Fetch messages without using cache
            messages = self.get_recent_messages(folder, limit, account_id, use_cache=False)
            self.logger.debug(f"Background refresh completed: {len(messages)} messages")
        except Exception as e:
            self.logger.error(f"Background message refresh failed: {e}")
    
    def get_cache_status(self, account_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get cache status for an account.
        
        Args:
            account_id: Account ID (uses default if None)
        
        Returns:
            Dictionary with cache statistics
        """
        account_id = account_id or self.default_account_id
        if not account_id:
            return {}
        
        return self.cache_manager.get_cache_stats(account_id)
    
    def clear_cache(self, account_id: Optional[int] = None):
        """
        Clear cache for an account.
        
        Args:
            account_id: Account ID (uses default if None)
        """
        account_id = account_id or self.default_account_id
        if not account_id:
            return
        
        self.cache_manager.clear_cache(account_id)
        self.logger.info(f"Cleared cache for account {account_id}")
    
    def force_refresh_folders(self, account_id: Optional[int] = None) -> List[FolderInfo]:
        """
        Force refresh folders from server and update cache.
        
        Args:
            account_id: Account ID (uses default if None)
        
        Returns:
            List of fresh folders from server
        """
        return self.get_folders(account_id, use_cache=False)
    
    def force_refresh_messages(self, folder: str = 'INBOX', limit: int = 50,
                              account_id: Optional[int] = None) -> List[EmailMessage]:
        """
        Force refresh messages from server and update cache.
        
        Args:
            folder: Folder to refresh
            limit: Number of messages to fetch
            account_id: Account ID (uses default if None)
        
        Returns:
            List of fresh messages from server
        """
        return self.get_recent_messages(folder, limit, account_id, use_cache=False) 