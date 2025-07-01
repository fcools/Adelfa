"""
Cache manager for email folders and messages.

Provides fast access to cached email data for immediate UI display,
with background synchronization for updates.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from ..data.models.cache import CachedFolder, CachedMessage
from ..core.email.imap_client import FolderInfo, EmailMessage, EmailHeader


class CacheManager:
    """Manages local caching of email folders and messages for fast startup."""
    
    def __init__(self, db_session: Session):
        """
        Initialize cache manager.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)
    
    # Folder caching methods
    
    def cache_folders(self, account_id: int, folders: List[FolderInfo]):
        """
        Cache folder list for an account.
        
        Args:
            account_id: Account ID
            folders: List of FolderInfo objects to cache
        """
        try:
            # Clear existing cached folders for this account
            self.db_session.query(CachedFolder).filter(
                CachedFolder.account_id == account_id
            ).delete()
            
            # Cache new folders
            for folder in folders:
                cached_folder = CachedFolder(
                    account_id=account_id,
                    name=folder.name,
                    delimiter=folder.delimiter,
                    flags=json.dumps(folder.flags),
                    exists=folder.exists,
                    recent=folder.recent,
                    unseen=folder.unseen,
                    uidvalidity=folder.uidvalidity,
                    uidnext=folder.uidnext,
                    last_updated=datetime.utcnow()
                )
                self.db_session.add(cached_folder)
            
            self.db_session.commit()
            self.logger.info(f"Cached {len(folders)} folders for account {account_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to cache folders: {e}")
            self.db_session.rollback()
    
    def get_cached_folders(self, account_id: int) -> List[FolderInfo]:
        """
        Get cached folders for an account.
        
        Args:
            account_id: Account ID
        
        Returns:
            List of FolderInfo objects from cache
        """
        try:
            cached_folders = self.db_session.query(CachedFolder).filter(
                CachedFolder.account_id == account_id
            ).order_by(CachedFolder.name).all()
            
            folders = []
            for cached in cached_folders:
                folder = FolderInfo(
                    name=cached.name,
                    delimiter=cached.delimiter,
                    flags=json.loads(cached.flags) if cached.flags else [],
                    exists=cached.exists,
                    recent=cached.recent,
                    unseen=cached.unseen,
                    uidvalidity=cached.uidvalidity,
                    uidnext=cached.uidnext
                )
                folders.append(folder)
            
            self.logger.debug(f"Retrieved {len(folders)} cached folders for account {account_id}")
            return folders
            
        except Exception as e:
            self.logger.error(f"Failed to get cached folders: {e}")
            return []
    
    def folders_cache_age(self, account_id: int) -> Optional[timedelta]:
        """
        Get the age of the cached folders.
        
        Args:
            account_id: Account ID
        
        Returns:
            Age of cache or None if no cache exists
        """
        try:
            latest_folder = self.db_session.query(CachedFolder).filter(
                CachedFolder.account_id == account_id
            ).order_by(desc(CachedFolder.last_updated)).first()
            
            if latest_folder:
                return datetime.utcnow() - latest_folder.last_updated
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get folder cache age: {e}")
            return None
    
    # Message caching methods
    
    def cache_messages(self, account_id: int, folder_name: str, messages: List[EmailMessage]):
        """
        Cache message headers for a folder.
        
        Args:
            account_id: Account ID
            folder_name: Folder name
            messages: List of EmailMessage objects to cache
        """
        try:
            # Get existing cached messages for this folder
            existing_uids = set()
            existing_messages = self.db_session.query(CachedMessage).filter(
                and_(
                    CachedMessage.account_id == account_id,
                    CachedMessage.folder_name == folder_name
                )
            ).all()
            
            # Create a map of existing messages by UID
            existing_map = {msg.uid: msg for msg in existing_messages}
            
            # Process new messages
            for message in messages:
                if message.uid in existing_map:
                    # Update existing message
                    cached_msg = existing_map[message.uid]
                    cached_msg.subject = message.headers.subject
                    cached_msg.from_addr = message.headers.from_addr
                    cached_msg.to_addrs = json.dumps(message.headers.to_addrs)
                    cached_msg.cc_addrs = json.dumps(message.headers.cc_addrs)
                    cached_msg.date = message.headers.date
                    cached_msg.flags = json.dumps(message.flags)
                    cached_msg.size = message.size
                    cached_msg.has_attachments = bool(message.attachments)
                    cached_msg.last_updated = datetime.utcnow()
                else:
                    # Add new message
                    cached_msg = CachedMessage(
                        account_id=account_id,
                        folder_name=folder_name,
                        uid=message.uid,
                        message_id=message.headers.message_id,
                        subject=message.headers.subject,
                        from_addr=message.headers.from_addr,
                        to_addrs=json.dumps(message.headers.to_addrs),
                        cc_addrs=json.dumps(message.headers.cc_addrs),
                        date=message.headers.date,
                        flags=json.dumps(message.flags),
                        size=message.size,
                        has_attachments=bool(message.attachments),
                        last_updated=datetime.utcnow()
                    )
                    self.db_session.add(cached_msg)
                
                existing_uids.add(message.uid)
            
            # Remove messages that are no longer on the server (optional)
            # For now, we'll keep old messages to avoid data loss
            
            self.db_session.commit()
            self.logger.info(f"Cached {len(messages)} messages for {folder_name} in account {account_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to cache messages: {e}")
            self.db_session.rollback()
    
    def get_cached_messages(self, account_id: int, folder_name: str, limit: int = 100) -> List[EmailMessage]:
        """
        Get cached messages for a folder.
        
        Args:
            account_id: Account ID
            folder_name: Folder name
            limit: Maximum number of messages to return
        
        Returns:
            List of EmailMessage objects from cache
        """
        try:
            cached_messages = self.db_session.query(CachedMessage).filter(
                and_(
                    CachedMessage.account_id == account_id,
                    CachedMessage.folder_name == folder_name
                )
            ).order_by(desc(CachedMessage.date)).limit(limit).all()
            
            messages = []
            for cached in cached_messages:
                # Reconstruct EmailHeader
                headers = EmailHeader(
                    message_id=cached.message_id or "",
                    subject=cached.subject or "",
                    from_addr=cached.from_addr or "",
                    to_addrs=json.loads(cached.to_addrs) if cached.to_addrs else [],
                    cc_addrs=json.loads(cached.cc_addrs) if cached.cc_addrs else [],
                    date=cached.date or datetime.utcnow()
                )
                
                # Reconstruct EmailMessage
                message = EmailMessage(
                    uid=cached.uid,
                    sequence_num=0,  # Not cached
                    folder=folder_name,
                    headers=headers,
                    flags=json.loads(cached.flags) if cached.flags else [],
                    size=cached.size,
                    attachments=[]  # Attachment details not cached for headers
                )
                messages.append(message)
            
            self.logger.debug(f"Retrieved {len(messages)} cached messages for {folder_name}")
            return messages
            
        except Exception as e:
            self.logger.error(f"Failed to get cached messages: {e}")
            return []
    
    def messages_cache_age(self, account_id: int, folder_name: str) -> Optional[timedelta]:
        """
        Get the age of the cached messages for a folder.
        
        Args:
            account_id: Account ID
            folder_name: Folder name
        
        Returns:
            Age of cache or None if no cache exists
        """
        try:
            latest_message = self.db_session.query(CachedMessage).filter(
                and_(
                    CachedMessage.account_id == account_id,
                    CachedMessage.folder_name == folder_name
                )
            ).order_by(desc(CachedMessage.last_updated)).first()
            
            if latest_message:
                return datetime.utcnow() - latest_message.last_updated
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get message cache age: {e}")
            return None
    
    def clear_cache(self, account_id: int):
        """
        Clear all cached data for an account.
        
        Args:
            account_id: Account ID
        """
        try:
            # Clear folders
            self.db_session.query(CachedFolder).filter(
                CachedFolder.account_id == account_id
            ).delete()
            
            # Clear messages
            self.db_session.query(CachedMessage).filter(
                CachedMessage.account_id == account_id
            ).delete()
            
            self.db_session.commit()
            self.logger.info(f"Cleared all cache for account {account_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            self.db_session.rollback()
    
    def get_cache_stats(self, account_id: int) -> Dict[str, Any]:
        """
        Get statistics about cached data for an account.
        
        Args:
            account_id: Account ID
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            folder_count = self.db_session.query(CachedFolder).filter(
                CachedFolder.account_id == account_id
            ).count()
            
            message_count = self.db_session.query(CachedMessage).filter(
                CachedMessage.account_id == account_id
            ).count()
            
            folders_age = self.folders_cache_age(account_id)
            
            return {
                'folder_count': folder_count,
                'message_count': message_count,
                'folders_cache_age_seconds': folders_age.total_seconds() if folders_age else None,
                'account_id': account_id
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return {
                'folder_count': 0,
                'message_count': 0,
                'folders_cache_age_seconds': None,
                'account_id': account_id
            } 