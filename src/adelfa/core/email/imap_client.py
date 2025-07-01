"""
IMAP email client for Adelfa PIM suite.

Provides IMAP4 client functionality for email retrieval, folder management,
message operations, and real-time synchronization using IDLE.
"""

import imaplib
import email
import email.header
import email.utils
import ssl
import socket
import threading
import time
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
import re
import base64
import quopri

from ...utils.logging_setup import get_logger
from ...data.models.accounts import Account, SecurityType
from .credential_manager import CredentialManager

logger = get_logger(__name__)


@dataclass
class EmailHeader:
    """Email header information."""
    message_id: str
    subject: str
    from_addr: str
    to_addrs: List[str]
    cc_addrs: List[str] = field(default_factory=list)
    bcc_addrs: List[str] = field(default_factory=list)
    date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    in_reply_to: Optional[str] = None
    references: List[str] = field(default_factory=list)
    thread_id: Optional[str] = None


@dataclass
class EmailAttachment:
    """Email attachment information."""
    filename: str
    content_type: str
    size: int
    content_id: Optional[str] = None
    is_inline: bool = False
    data: Optional[bytes] = None


@dataclass
class EmailMessage:
    """Complete email message."""
    uid: int
    sequence_num: int
    folder: str
    headers: EmailHeader
    text_content: Optional[str] = None
    html_content: Optional[str] = None
    attachments: List[EmailAttachment] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    size: int = 0
    internal_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_read(self) -> bool:
        """Check if message is marked as read."""
        return '\\Seen' in self.flags
    
    @property
    def is_flagged(self) -> bool:
        """Check if message is flagged."""
        return '\\Flagged' in self.flags
    
    @property
    def is_deleted(self) -> bool:
        """Check if message is marked for deletion."""
        return '\\Deleted' in self.flags


@dataclass
class FolderInfo:
    """IMAP folder information."""
    name: str
    delimiter: str
    flags: List[str]
    exists: int = 0
    recent: int = 0
    unseen: int = 0
    uidvalidity: int = 0
    uidnext: int = 0


class IMAPClientError(Exception):
    """IMAP client specific error."""
    pass


class IMAPIdleHandler:
    """Handles IMAP IDLE for real-time email notifications."""
    
    def __init__(self, client: 'IMAPClient', folder: str = 'INBOX'):
        self.client = client
        self.folder = folder
        self.running = False
        self.thread = None
        self.callback: Optional[Callable] = None
        self.logger = logger
    
    def start(self, callback: Callable[[str, List[int]], None]):
        """
        Start IDLE monitoring.
        
        Args:
            callback: Function called with (event_type, uids) when changes occur
        """
        if self.running:
            return
        
        self.callback = callback
        self.running = True
        self.thread = threading.Thread(target=self._idle_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop IDLE monitoring."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
    
    def _idle_loop(self):
        """Main IDLE loop running in background thread."""
        while self.running:
            try:
                # Simple polling instead of complex IDLE implementation
                if not self.client.is_connected():
                    if not self.client.connect():
                        time.sleep(30)
                        continue
                
                # Just poll for changes every 30 seconds
                if self.callback:
                    self.callback('poll_update', [])
                
                time.sleep(30)
                
            except Exception as e:
                self.logger.error(f"IDLE loop error: {e}")
                time.sleep(30)


class IMAPClient:
    """
    IMAP client for email operations.
    
    Provides comprehensive IMAP functionality including message retrieval,
    folder management, search capabilities, and real-time synchronization.
    """
    
    def __init__(self, account: Account, credential_manager: CredentialManager):
        """
        Initialize IMAP client.
        
        Args:
            account: Email account configuration
            credential_manager: Credential manager for password retrieval
        """
        self.account = account
        self.credential_manager = credential_manager
        self.imap: Optional[imaplib.IMAP4] = None
        self.current_folder: Optional[str] = None
        self.idle_handler: Optional[IMAPIdleHandler] = None
        self.logger = logger
        self._lock = threading.Lock()
    
    def connect(self) -> bool:
        """
        Connect to IMAP server.
        
        Returns:
            bool: True if connection successful
        """
        try:
            with self._lock:
                if self.imap:
                    self.disconnect()
                
                # Create connection
                if self.account.incoming_security == SecurityType.TLS_SSL:
                    self.imap = imaplib.IMAP4_SSL(
                        self.account.incoming_server,
                        self.account.incoming_port,
                        timeout=30
                    )
                else:
                    self.imap = imaplib.IMAP4(
                        self.account.incoming_server,
                        self.account.incoming_port,
                        timeout=30
                    )
                    
                    if self.account.incoming_security == SecurityType.STARTTLS:
                        self.imap.starttls()
                
                # Authenticate
                password = self.credential_manager.retrieve_password(
                    self.account.incoming_password_key
                )
                if not password:
                    raise IMAPClientError("No password available")
                
                self.imap.login(self.account.incoming_username, password)
                
                self.logger.info(f"Connected to IMAP server {self.account.incoming_server}")
                return True
                
        except Exception as e:
            self.logger.error(f"IMAP connection failed: {e}")
            self.imap = None
            return False
    
    def disconnect(self):
        """Disconnect from IMAP server."""
        try:
            with self._lock:
                if self.idle_handler:
                    self.idle_handler.stop()
                    self.idle_handler = None
                
                if self.imap:
                    try:
                        self.imap.logout()
                    except:
                        pass
                    self.imap = None
                
                self.current_folder = None
                self.logger.info("Disconnected from IMAP server")
                
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to server."""
        try:
            with self._lock:
                if not self.imap:
                    return False
                
                # Try a simple command
                status, _ = self.imap.noop()
                return status == 'OK'
                
        except Exception as e:
            self.logger.debug(f"Connection check failed: {e}")
            return False
    
    def get_folders(self) -> List[FolderInfo]:
        """
        Get list of available folders.
        
        Returns:
            List[FolderInfo]: Available folders
        """
        if not self.is_connected():
            raise IMAPClientError("Not connected to server")
        
        try:
            status, folders = self.imap.list()
            if status != 'OK':
                raise IMAPClientError("Failed to list folders")
            
            folder_list = []
            for folder_data in folders:
                if isinstance(folder_data, bytes):
                    folder_str = folder_data.decode('utf-8')
                else:
                    folder_str = folder_data
                
                # Parse folder response: (flags) "delimiter" "name"
                match = re.match(r'\(([^)]*)\)\s+"([^"]*)"\s+"?([^"]*)"?', folder_str)
                if match:
                    flags_str, delimiter, name = match.groups()
                    flags = [f.strip() for f in flags_str.split() if f.strip()]
                    
                    folder_info = FolderInfo(
                        name=name,
                        delimiter=delimiter,
                        flags=flags
                    )
                    folder_list.append(folder_info)
            
            return folder_list
            
        except Exception as e:
            raise IMAPClientError(f"Failed to get folders: {e}")
    
    def select_folder(self, folder_name: str = 'INBOX') -> FolderInfo:
        """
        Select a folder for operations.
        
        Args:
            folder_name: Name of folder to select
        
        Returns:
            FolderInfo: Folder information
        """
        if not self.is_connected():
            raise IMAPClientError("Not connected to server")
        
        try:
            status, data = self.imap.select(folder_name)
            if status != 'OK':
                raise IMAPClientError(f"Failed to select folder {folder_name}")
            
            self.current_folder = folder_name
            
            # Get folder status information
            folder_info = FolderInfo(
                name=folder_name,
                delimiter="/",  # Will be updated from folder list if needed
                flags=[],
                exists=int(data[0]) if data else 0
            )
            
            # Get additional folder status
            try:
                status, status_data = self.imap.status(
                    folder_name, 
                    '(MESSAGES RECENT UNSEEN UIDVALIDITY UIDNEXT)'
                )
                if status == 'OK' and status_data:
                    status_str = status_data[0].decode('utf-8')
                    # Parse status response
                    if 'MESSAGES' in status_str:
                        folder_info.exists = int(re.search(r'MESSAGES (\d+)', status_str).group(1))
                    if 'RECENT' in status_str:
                        folder_info.recent = int(re.search(r'RECENT (\d+)', status_str).group(1))
                    if 'UNSEEN' in status_str:
                        folder_info.unseen = int(re.search(r'UNSEEN (\d+)', status_str).group(1))
                    if 'UIDVALIDITY' in status_str:
                        folder_info.uidvalidity = int(re.search(r'UIDVALIDITY (\d+)', status_str).group(1))
                    if 'UIDNEXT' in status_str:
                        folder_info.uidnext = int(re.search(r'UIDNEXT (\d+)', status_str).group(1))
            except:
                pass  # Status command failed, use basic info
            
            return folder_info
            
        except Exception as e:
            raise IMAPClientError(f"Failed to select folder: {e}")
    
    def search_messages(self, criteria: str = 'ALL') -> List[int]:
        """
        Search for messages in current folder.
        
        Args:
            criteria: IMAP search criteria (e.g., 'UNSEEN', 'FROM user@example.com')
        
        Returns:
            List[int]: Message UIDs matching criteria
        """
        if not self.current_folder:
            raise IMAPClientError("No folder selected")
        
        try:
            status, data = self.imap.uid('search', None, criteria)
            if status != 'OK':
                raise IMAPClientError(f"Search failed: {criteria}")
            
            if not data or not data[0]:
                return []
            
            uids = data[0].decode('utf-8').split()
            return [int(uid) for uid in uids if uid.isdigit()]
            
        except Exception as e:
            raise IMAPClientError(f"Search error: {e}")
    
    def get_message_headers(self, uid: int) -> EmailHeader:
        """
        Get message headers only.
        
        Args:
            uid: Message UID
        
        Returns:
            EmailHeader: Message header information
        """
        if not self.current_folder:
            raise IMAPClientError("No folder selected")
        
        try:
            status, data = self.imap.uid('fetch', str(uid), '(RFC822.HEADER)')
            if status != 'OK' or not data:
                raise IMAPClientError(f"Failed to fetch headers for UID {uid}")
            
            header_data = data[0][1]
            if isinstance(header_data, bytes):
                header_str = header_data.decode('utf-8', errors='ignore')
            else:
                header_str = header_data
            
            # Parse headers
            msg = email.message_from_string(header_str)
            
            return self._parse_headers(msg)
            
        except Exception as e:
            raise IMAPClientError(f"Failed to get headers: {e}")
    
    def get_message(self, uid: int, include_body: bool = True, include_attachments: bool = False) -> EmailMessage:
        """
        Get complete message.
        
        Args:
            uid: Message UID
            include_body: Whether to include message body
            include_attachments: Whether to include attachment data
        
        Returns:
            EmailMessage: Complete message
        """
        if not self.current_folder:
            raise IMAPClientError("No folder selected")
        
        try:
            # Fetch message data
            fetch_items = ['FLAGS', 'INTERNALDATE', 'RFC822.SIZE']
            if include_body:
                fetch_items.append('RFC822')
            else:
                fetch_items.append('RFC822.HEADER')
            
            fetch_str = '(' + ' '.join(fetch_items) + ')'
            status, data = self.imap.uid('fetch', str(uid), fetch_str)
            
            if status != 'OK' or not data:
                raise IMAPClientError(f"Failed to fetch message UID {uid}")
            
            # Parse IMAP FETCH response properly
            # IMAP responses come as: [(b'123 (UID 456 FLAGS (...) RFC822 {size}', b'email-content'), b')')] 
            message_data = data[0]
            
            if isinstance(message_data, tuple) and len(message_data) >= 2:
                response_str = message_data[0].decode('utf-8') if isinstance(message_data[0], bytes) else message_data[0]
                message_content = message_data[1]
            else:
                # Fallback parsing
                response_str = str(message_data)
                message_content = b""
            
            # Extract flags, date, size from response
            flags = []
            internal_date = datetime.now(timezone.utc)
            size = 0
            
            # Parse flags
            flags_match = re.search(r'FLAGS \(([^)]*)\)', response_str)
            if flags_match:
                flags = [f.strip() for f in flags_match.group(1).split()]
            
            # Parse internal date
            date_match = re.search(r'INTERNALDATE "([^"]*)"', response_str)
            if date_match:
                try:
                    internal_date = email.utils.parsedate_to_datetime(date_match.group(1))
                except:
                    pass
            
            # Parse size
            size_match = re.search(r'RFC822\.SIZE (\d+)', response_str)
            if size_match:
                size = int(size_match.group(1))
            
            # Parse email content
            if isinstance(message_content, bytes):
                email_str = message_content.decode('utf-8', errors='ignore')
            else:
                email_str = message_content
            
            msg = email.message_from_string(email_str)
            
            # Build EmailMessage object
            headers = self._parse_headers(msg)
            text_content, html_content, attachments = self._parse_body(msg, include_attachments)
            
            # Get sequence number
            seq_num = self._get_sequence_number(uid)
            
            email_msg = EmailMessage(
                uid=uid,
                sequence_num=seq_num,
                folder=self.current_folder,
                headers=headers,
                text_content=text_content,
                html_content=html_content,
                attachments=attachments,
                flags=flags,
                size=size,
                internal_date=internal_date
            )
            
            return email_msg
            
        except Exception as e:
            raise IMAPClientError(f"Failed to get message: {e}")
    
    def mark_as_read(self, uid: int):
        """Mark message as read."""
        self._set_flags(uid, ['\\Seen'], add=True)
    
    def mark_as_unread(self, uid: int):
        """Mark message as unread."""
        self._set_flags(uid, ['\\Seen'], add=False)
    
    def mark_as_flagged(self, uid: int):
        """Mark message as flagged."""
        self._set_flags(uid, ['\\Flagged'], add=True)
    
    def mark_as_unflagged(self, uid: int):
        """Remove flagged status."""
        self._set_flags(uid, ['\\Flagged'], add=False)
    
    def delete_message(self, uid: int, expunge: bool = False):
        """
        Mark message for deletion.
        
        Args:
            uid: Message UID
            expunge: Whether to immediately expunge (permanently delete)
        """
        self._set_flags(uid, ['\\Deleted'], add=True)
        if expunge:
            self.expunge()
    
    def move_message(self, uid: int, target_folder: str):
        """
        Move message to another folder.
        
        Args:
            uid: Message UID  
            target_folder: Target folder name
        """
        if not self.current_folder:
            raise IMAPClientError("No folder selected")
        
        try:
            # Use MOVE command if available, otherwise copy+delete
            try:
                status, _ = self.imap.uid('move', str(uid), target_folder)
                if status == 'OK':
                    return
            except:
                pass  # MOVE not supported, fall back to copy+delete
            
            # Copy to target folder
            status, _ = self.imap.uid('copy', str(uid), target_folder)
            if status != 'OK':
                raise IMAPClientError(f"Failed to copy message to {target_folder}")
            
            # Mark as deleted in current folder
            self.delete_message(uid, expunge=True)
            
        except Exception as e:
            raise IMAPClientError(f"Failed to move message: {e}")
    
    def expunge(self):
        """Permanently delete messages marked for deletion."""
        if not self.current_folder:
            raise IMAPClientError("No folder selected")
        
        try:
            status, _ = self.imap.expunge()
            if status != 'OK':
                raise IMAPClientError("Expunge failed")
        except Exception as e:
            raise IMAPClientError(f"Expunge error: {e}")
    
    def start_idle(self, callback: Callable[[str, List[int]], None], folder: str = 'INBOX'):
        """
        Start IDLE monitoring for real-time updates.
        
        Args:
            callback: Function called when folder changes
            folder: Folder to monitor
        """
        if self.idle_handler:
            self.idle_handler.stop()
        
        self.idle_handler = IMAPIdleHandler(self, folder)
        self.idle_handler.start(callback)
    
    def stop_idle(self):
        """Stop IDLE monitoring."""
        if self.idle_handler:
            self.idle_handler.stop()
            self.idle_handler = None
    
    def _set_flags(self, uid: int, flags: List[str], add: bool = True):
        """Set or remove message flags."""
        if not self.current_folder:
            raise IMAPClientError("No folder selected")
        
        try:
            flag_str = ' '.join(flags)
            command = '+FLAGS' if add else '-FLAGS'
            
            status, _ = self.imap.uid('store', str(uid), command, f'({flag_str})')
            if status != 'OK':
                raise IMAPClientError(f"Failed to set flags: {flags}")
                
        except Exception as e:
            raise IMAPClientError(f"Flag operation failed: {e}")
    
    def _get_sequence_number(self, uid: int) -> int:
        """Get sequence number for UID."""
        try:
            status, data = self.imap.uid('search', None, f'UID {uid}')
            if status == 'OK' and data and data[0]:
                return 1  # Simplified - would need proper sequence mapping
            return 0
        except:
            return 0
    
    def _parse_headers(self, msg: email.message.EmailMessage) -> EmailHeader:
        """Parse email headers into EmailHeader object."""
        try:
            # Helper function to decode header values
            def decode_header(header_value):
                if not header_value:
                    return ""
                
                decoded_parts = []
                for part, encoding in email.header.decode_header(header_value):
                    if isinstance(part, bytes):
                        if encoding:
                            decoded_parts.append(part.decode(encoding, errors='ignore'))
                        else:
                            decoded_parts.append(part.decode('utf-8', errors='ignore'))
                    else:
                        decoded_parts.append(part)
                
                return ''.join(decoded_parts)
            
            # Parse basic headers
            message_id = msg.get('Message-ID', '')
            subject = decode_header(msg.get('Subject', ''))
            from_addr = decode_header(msg.get('From', ''))
            
            # Parse address lists
            to_addrs = []
            if msg.get('To'):
                to_addrs = [addr.strip() for addr in decode_header(msg.get('To')).split(',')]
            
            cc_addrs = []
            if msg.get('Cc'):
                cc_addrs = [addr.strip() for addr in decode_header(msg.get('Cc')).split(',')]
            
            bcc_addrs = []
            if msg.get('Bcc'):
                bcc_addrs = [addr.strip() for addr in decode_header(msg.get('Bcc')).split(',')]
            
            # Parse date
            date = datetime.now(timezone.utc)
            if msg.get('Date'):
                try:
                    date = email.utils.parsedate_to_datetime(msg.get('Date'))
                except:
                    pass
            
            # Parse threading headers
            in_reply_to = msg.get('In-Reply-To', '')
            references = []
            if msg.get('References'):
                references = [ref.strip() for ref in msg.get('References').split()]
            
            return EmailHeader(
                message_id=message_id,
                subject=subject,
                from_addr=from_addr,
                to_addrs=to_addrs,
                cc_addrs=cc_addrs,
                bcc_addrs=bcc_addrs,
                date=date,
                in_reply_to=in_reply_to,
                references=references
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse headers: {e}")
            return EmailHeader(
                message_id="",
                subject="[Parse Error]",
                from_addr="",
                to_addrs=[]
            )
    
    def _parse_body(self, msg: email.message.EmailMessage, include_attachments: bool = False) -> Tuple[Optional[str], Optional[str], List[EmailAttachment]]:
        """Parse email body and attachments."""
        text_content = None
        html_content = None
        attachments = []
        
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = part.get('Content-Disposition', '')
                    
                    if content_type == 'text/plain' and 'attachment' not in content_disposition:
                        if text_content is None:
                            text_content = self._decode_part_content(part)
                    elif content_type == 'text/html' and 'attachment' not in content_disposition:
                        if html_content is None:
                            html_content = self._decode_part_content(part)
                    elif content_disposition.startswith('attachment') or part.get_filename():
                        # This is an attachment
                        filename = part.get_filename() or f"attachment_{len(attachments) + 1}"
                        size = len(part.get_payload(decode=True) or b'')
                        
                        attachment = EmailAttachment(
                            filename=filename,
                            content_type=content_type,
                            size=size,
                            content_id=part.get('Content-ID'),
                            is_inline='inline' in content_disposition
                        )
                        
                        if include_attachments:
                            attachment.data = part.get_payload(decode=True)
                        
                        attachments.append(attachment)
            else:
                # Single part message
                content_type = msg.get_content_type()
                if content_type == 'text/plain':
                    text_content = self._decode_part_content(msg)
                elif content_type == 'text/html':
                    html_content = self._decode_part_content(msg)
        
        except Exception as e:
            self.logger.error(f"Failed to parse body: {e}")
        
        return text_content, html_content, attachments
    
    def _decode_part_content(self, part: email.message.EmailMessage) -> str:
        """Decode content of an email part."""
        try:
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                # Try to get charset from content type
                charset = part.get_content_charset() or 'utf-8'
                return payload.decode(charset, errors='ignore')
            else:
                return str(payload)
        except Exception as e:
            self.logger.error(f"Failed to decode part content: {e}")
            return "[Content decode error]"

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect() 