"""
Enhanced email cache management for Adelfa PIM suite.

Provides caching for email content, images, and user preferences.
Also maintains backward compatibility with the original folder/message caching.
"""

import os
import sqlite3
import hashlib
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from ..config.app_config import AppConfig
from ..data.models.cache import CachedFolder, CachedMessage
from .email.imap_client import FolderInfo, EmailMessage, EmailHeader


@dataclass
class CachedEmail:
    """Represents a cached email with metadata."""
    uid: int
    account_id: int
    folder: str
    subject: str
    from_addr: str
    date: str
    size: int
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    attachments: Optional[str] = None  # JSON serialized
    is_read: bool = False
    is_flagged: bool = False
    cached_at: float = 0.0
    content_hash: str = ""


@dataclass
class CachedImage:
    """Represents a cached email image."""
    url: str
    email_hash: str
    content_type: str
    data: bytes
    cached_at: float
    size: int


class EmailCacheManager:
    """
    Manages email caching and image loading preferences.
    
    Provides persistent storage for emails, images, and user decisions
    about loading external content.
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the cache manager.
        
        Args:
            config: Application configuration instance
        """
        self.config = config
        self.cache_dir = config.get_cache_dir()
        self.db_path = self.cache_dir / "email_cache.db"
        self.images_dir = self.cache_dir / "images"
        self.images_dir.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize database
        self._init_database()
        
    def _init_database(self):
        """Initialize the cache database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cached_emails (
                        uid INTEGER,
                        account_id INTEGER,
                        folder TEXT,
                        subject TEXT,
                        from_addr TEXT,
                        date TEXT,
                        size INTEGER,
                        html_content TEXT,
                        text_content TEXT,
                        attachments TEXT,
                        is_read BOOLEAN,
                        is_flagged BOOLEAN,
                        cached_at REAL,
                        content_hash TEXT,
                        PRIMARY KEY (uid, account_id, folder)
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cached_images (
                        url TEXT,
                        email_hash TEXT,
                        content_type TEXT,
                        data BLOB,
                        cached_at REAL,
                        size INTEGER,
                        PRIMARY KEY (url, email_hash)
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS image_decisions (
                        email_hash TEXT PRIMARY KEY,
                        load_images BOOLEAN,
                        decided_at REAL
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS link_decisions (
                        email_hash TEXT PRIMARY KEY,
                        enable_links BOOLEAN,
                        decided_at REAL
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to initialize cache database: {e}")
    
    def _get_email_hash(self, uid: int, account_id: int, folder: str) -> str:
        """Generate a unique hash for an email."""
        content = f"{uid}:{account_id}:{folder}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def cache_email(self, email_data: Dict[str, Any]) -> bool:
        """
        Cache an email in the database.
        
        Args:
            email_data: Email data dictionary
            
        Returns:
            bool: True if cached successfully
        """
        if not self.config.email.cache_enabled:
            return False
            
        try:
            # Create content hash for change detection
            content = str(email_data.get('html_content', '')) + str(email_data.get('text_content', ''))
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            cached_email = CachedEmail(
                uid=email_data['uid'],
                account_id=email_data['account_id'],
                folder=email_data['folder'],
                subject=email_data.get('subject', ''),
                from_addr=email_data.get('from_addr', ''),
                date=email_data.get('date', ''),
                size=email_data.get('size', 0),
                html_content=email_data.get('html_content'),
                text_content=email_data.get('text_content'),
                attachments=json.dumps(email_data.get('attachments', [])),
                is_read=email_data.get('is_read', False),
                is_flagged=email_data.get('is_flagged', False),
                cached_at=time.time(),
                content_hash=content_hash
            )
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cached_emails 
                    (uid, account_id, folder, subject, from_addr, date, size,
                     html_content, text_content, attachments, is_read, is_flagged,
                     cached_at, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cached_email.uid, cached_email.account_id, cached_email.folder,
                    cached_email.subject, cached_email.from_addr, cached_email.date,
                    cached_email.size, cached_email.html_content, cached_email.text_content,
                    cached_email.attachments, cached_email.is_read, cached_email.is_flagged,
                    cached_email.cached_at, cached_email.content_hash
                ))
                conn.commit()
                
            self._cleanup_cache_if_needed()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cache email: {e}")
            return False
    
    def get_cached_email(self, uid: int, account_id: int, folder: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached email.
        
        Args:
            uid: Email UID
            account_id: Account ID
            folder: Folder name
            
        Returns:
            Optional[Dict]: Email data if cached, None otherwise
        """
        if not self.config.email.cache_enabled:
            return None
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM cached_emails 
                    WHERE uid = ? AND account_id = ? AND folder = ?
                """, (uid, account_id, folder))
                
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    email_data = dict(zip(columns, row))
                    
                    # Parse attachments JSON
                    if email_data['attachments']:
                        email_data['attachments'] = json.loads(email_data['attachments'])
                    else:
                        email_data['attachments'] = []
                        
                    return email_data
                    
        except Exception as e:
            self.logger.error(f"Failed to get cached email: {e}")
            
        return None
    
    def cache_image(self, url: str, email_hash: str, content_type: str, data: bytes) -> bool:
        """
        Cache an image from an email.
        
        Args:
            url: Image URL
            email_hash: Hash of the email containing the image
            content_type: MIME type of the image
            data: Image binary data
            
        Returns:
            bool: True if cached successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cached_images 
                    (url, email_hash, content_type, data, cached_at, size)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (url, email_hash, content_type, data, time.time(), len(data)))
                conn.commit()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cache image: {e}")
            return False
    
    def get_cached_image(self, url: str, email_hash: str) -> Optional[Tuple[str, bytes]]:
        """
        Retrieve a cached image.
        
        Args:
            url: Image URL
            email_hash: Hash of the email containing the image
            
        Returns:
            Optional[Tuple]: (content_type, data) if cached, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT content_type, data FROM cached_images 
                    WHERE url = ? AND email_hash = ?
                """, (url, email_hash))
                
                row = cursor.fetchone()
                if row:
                    return row[0], row[1]
                    
        except Exception as e:
            self.logger.error(f"Failed to get cached image: {e}")
            
        return None
    
    def set_image_decision(self, email_hash: str, load_images: bool):
        """
        Save user's decision about loading images for a specific email.
        
        Args:
            email_hash: Hash of the email
            load_images: Whether to load images for this email
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO image_decisions 
                    (email_hash, load_images, decided_at)
                    VALUES (?, ?, ?)
                """, (email_hash, load_images, time.time()))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to save image decision: {e}")
    
    def get_image_decision(self, email_hash: str) -> Optional[bool]:
        """
        Get user's previous decision about loading images for an email.
        
        Args:
            email_hash: Hash of the email
            
        Returns:
            Optional[bool]: True to load, False to block, None if not decided
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT load_images FROM image_decisions 
                    WHERE email_hash = ?
                """, (email_hash,))
                
                row = cursor.fetchone()
                if row:
                    return bool(row[0])
                    
        except Exception as e:
            self.logger.error(f"Failed to get image decision: {e}")
            
        return None
    
    def set_link_decision(self, email_hash: str, enable_links: bool):
        """
        Save user's decision about enabling links for a specific email.
        
        Args:
            email_hash: Hash of the email
            enable_links: Whether to enable links for this email
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO link_decisions 
                    (email_hash, enable_links, decided_at)
                    VALUES (?, ?, ?)
                """, (email_hash, enable_links, time.time()))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to save link decision: {e}")
    
    def get_link_decision(self, email_hash: str) -> Optional[bool]:
        """
        Get user's previous decision about enabling links for an email.
        
        Args:
            email_hash: Hash of the email
            
        Returns:
            Optional[bool]: True to enable, False to disable, None if not decided
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT enable_links FROM link_decisions 
                    WHERE email_hash = ?
                """, (email_hash,))
                
                row = cursor.fetchone()
                if row:
                    return bool(row[0])
                    
        except Exception as e:
            self.logger.error(f"Failed to get link decision: {e}")
            
        return None
    
    def _cleanup_cache_if_needed(self):
        """Clean up cache if it exceeds the configured size limit."""
        try:
            # Get cache size
            total_size = 0
            for table in ['cached_emails', 'cached_images']:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(f"SELECT SUM(size) FROM {table}")
                    size = cursor.fetchone()[0] or 0
                    total_size += size
            
            # Convert to MB
            total_size_mb = total_size / (1024 * 1024)
            
            if total_size_mb > self.config.email.cache_size_mb:
                self._cleanup_old_entries()
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup cache: {e}")
    
    def _cleanup_old_entries(self):
        """Remove oldest cache entries to free space."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Remove oldest 25% of emails
                conn.execute("""
                    DELETE FROM cached_emails 
                    WHERE cached_at < (
                        SELECT cached_at FROM cached_emails 
                        ORDER BY cached_at DESC 
                        LIMIT 1 OFFSET (SELECT COUNT(*) / 4 FROM cached_emails)
                    )
                """)
                
                # Remove oldest 25% of images
                conn.execute("""
                    DELETE FROM cached_images 
                    WHERE cached_at < (
                        SELECT cached_at FROM cached_images 
                        ORDER BY cached_at DESC 
                        LIMIT 1 OFFSET (SELECT COUNT(*) / 4 FROM cached_images)
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old entries: {e}")
    
    def clear_cache(self):
        """Clear all cached data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cached_emails")
                conn.execute("DELETE FROM cached_images")
                conn.execute("DELETE FROM image_decisions")
                conn.execute("DELETE FROM link_decisions")
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            'emails_count': 0,
            'images_count': 0,
            'total_size_mb': 0,
            'enabled': self.config.email.cache_enabled
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Count emails
                cursor = conn.execute("SELECT COUNT(*) FROM cached_emails")
                stats['emails_count'] = cursor.fetchone()[0]
                
                # Count images
                cursor = conn.execute("SELECT COUNT(*) FROM cached_images")
                stats['images_count'] = cursor.fetchone()[0]
                
                # Calculate total size
                cursor = conn.execute("""
                    SELECT 
                        (SELECT COALESCE(SUM(size), 0) FROM cached_emails) +
                        (SELECT COALESCE(SUM(size), 0) FROM cached_images) as total_size
                """)
                total_size = cursor.fetchone()[0] or 0
                stats['total_size_mb'] = total_size / (1024 * 1024)
                
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            
        return stats


class CacheManager:
    """Legacy cache manager for email folders and messages (backward compatibility)."""
    
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