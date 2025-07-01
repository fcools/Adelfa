"""
SMTP email client for Adelfa PIM suite.

Provides SMTP client functionality for sending emails with authentication,
security, and attachment support.
"""

import smtplib
import email
import email.mime.text
import email.mime.multipart
import email.mime.base
import email.mime.image
import email.encoders
import ssl
import socket
import mimetypes
import os
from typing import List, Optional, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from ...utils.logging_setup import get_logger
from ...data.models.accounts import Account, SecurityType
from .credential_manager import CredentialManager

logger = get_logger(__name__)


@dataclass
class EmailAddress:
    """Email address with optional display name."""
    email: str
    name: Optional[str] = None
    
    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email


@dataclass
class EmailAttachment:
    """Email attachment for sending."""
    filename: str
    filepath: Optional[str] = None
    content: Optional[bytes] = None
    content_type: Optional[str] = None
    content_id: Optional[str] = None
    is_inline: bool = False
    
    def __post_init__(self):
        if self.content_type is None and self.filename:
            self.content_type, _ = mimetypes.guess_type(self.filename)
            if self.content_type is None:
                self.content_type = 'application/octet-stream'


@dataclass 
class OutgoingEmail:
    """Email message for sending."""
    subject: str
    from_addr: EmailAddress
    to_addrs: List[EmailAddress]
    cc_addrs: List[EmailAddress] = field(default_factory=list)
    bcc_addrs: List[EmailAddress] = field(default_factory=list)
    reply_to: Optional[EmailAddress] = None
    text_content: Optional[str] = None
    html_content: Optional[str] = None
    attachments: List[EmailAttachment] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    priority: str = 'normal'  # high, normal, low
    request_receipt: bool = False
    
    @property
    def all_recipients(self) -> List[EmailAddress]:
        """Get all recipients (To, CC, BCC)."""
        return self.to_addrs + self.cc_addrs + self.bcc_addrs


class SMTPClientError(Exception):
    """SMTP client specific error."""
    pass


class SMTPClient:
    """
    SMTP client for sending emails.
    
    Provides comprehensive SMTP functionality including authentication,
    security, HTML/text emails, and attachment support.
    """
    
    def __init__(self, account: Account, credential_manager: CredentialManager):
        """
        Initialize SMTP client.
        
        Args:
            account: Email account configuration
            credential_manager: Credential manager for password retrieval
        """
        self.account = account
        self.credential_manager = credential_manager
        self.smtp: Optional[smtplib.SMTP] = None
        self.logger = logger
    
    def connect(self) -> bool:
        """
        Connect to SMTP server.
        
        Returns:
            bool: True if connection successful
        """
        try:
            if self.smtp:
                self.disconnect()
            
            # Create connection
            if self.account.outgoing_security == SecurityType.TLS_SSL:
                self.smtp = smtplib.SMTP_SSL(
                    self.account.outgoing_server,
                    self.account.outgoing_port,
                    timeout=30
                )
            else:
                self.smtp = smtplib.SMTP(
                    self.account.outgoing_server,
                    self.account.outgoing_port,
                    timeout=30
                )
                
                if self.account.outgoing_security == SecurityType.STARTTLS:
                    self.smtp.starttls()
            
            # Authenticate if required
            if self.account.outgoing_auth_required:
                password = self.credential_manager.retrieve_password(
                    self.account.outgoing_password_key
                )
                if not password:
                    raise SMTPClientError("No password available")
                
                username = self.account.outgoing_username or self.account.incoming_username
                self.smtp.login(username, password)
            
            self.logger.info(f"Connected to SMTP server {self.account.outgoing_server}")
            return True
            
        except Exception as e:
            self.logger.error(f"SMTP connection failed: {e}")
            self.smtp = None
            return False
    
    def disconnect(self):
        """Disconnect from SMTP server."""
        try:
            if self.smtp:
                try:
                    self.smtp.quit()
                except:
                    pass
                self.smtp = None
            
            self.logger.info("Disconnected from SMTP server")
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to server."""
        try:
            if not self.smtp:
                return False
            
            # Try a simple command
            status, _ = self.smtp.noop()
            return status == 250
            
        except:
            return False
    
    def send_email(self, email_msg: OutgoingEmail) -> bool:
        """
        Send an email message.
        
        Args:
            email_msg: Email message to send
        
        Returns:
            bool: True if sent successfully
        """
        if not self.is_connected():
            raise SMTPClientError("Not connected to server")
        
        try:
            # Build MIME message
            mime_msg = self._build_mime_message(email_msg)
            
            # Get recipient email addresses
            recipients = [addr.email for addr in email_msg.all_recipients]
            
            # Send the message
            refused = self.smtp.send_message(
                mime_msg,
                from_addr=email_msg.from_addr.email,
                to_addrs=recipients
            )
            
            if refused:
                self.logger.warning(f"Some recipients refused: {refused}")
                return len(refused) < len(recipients)  # Partial success
            
            self.logger.info(f"Email sent successfully to {len(recipients)} recipients")
            return True
            
        except Exception as e:
            raise SMTPClientError(f"Failed to send email: {e}")
    
    def send_test_email(self, to_email: str) -> bool:
        """
        Send a test email to verify connection.
        
        Args:
            to_email: Recipient email address
        
        Returns:
            bool: True if sent successfully
        """
        test_email = OutgoingEmail(
            subject="Adelfa Email Test",
            from_addr=EmailAddress(
                email=self.account.email_address,
                name=self.account.display_name
            ),
            to_addrs=[EmailAddress(email=to_email)],
            text_content="This is a test email from Adelfa PIM suite.\n\nIf you receive this message, your email configuration is working correctly.",
            html_content="""
            <html>
            <body>
                <h2>Adelfa Email Test</h2>
                <p>This is a test email from <strong>Adelfa PIM suite</strong>.</p>
                <p>If you receive this message, your email configuration is working correctly.</p>
                <hr>
                <p><em>Sent at: {}</em></p>
            </body>
            </html>
            """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        
        return self.send_email(test_email)
    
    def _build_mime_message(self, email_msg: OutgoingEmail) -> email.mime.multipart.MIMEMultipart:
        """Build MIME message from OutgoingEmail."""
        # Create main message container
        if email_msg.attachments or (email_msg.text_content and email_msg.html_content):
            msg = email.mime.multipart.MIMEMultipart('mixed')
        else:
            msg = email.mime.multipart.MIMEMultipart('alternative')
        
        # Set headers
        msg['Subject'] = email_msg.subject
        msg['From'] = str(email_msg.from_addr)
        msg['To'] = ', '.join(str(addr) for addr in email_msg.to_addrs)
        
        if email_msg.cc_addrs:
            msg['Cc'] = ', '.join(str(addr) for addr in email_msg.cc_addrs)
        
        if email_msg.reply_to:
            msg['Reply-To'] = str(email_msg.reply_to)
        
        msg['Date'] = email.utils.formatdate(localtime=True)
        msg['Message-ID'] = email.utils.make_msgid()
        
        # Set priority
        if email_msg.priority == 'high':
            msg['X-Priority'] = '1'
            msg['Importance'] = 'high'
        elif email_msg.priority == 'low':
            msg['X-Priority'] = '5'
            msg['Importance'] = 'low'
        
        # Request read receipt
        if email_msg.request_receipt:
            msg['Return-Receipt-To'] = email_msg.from_addr.email
            msg['Disposition-Notification-To'] = email_msg.from_addr.email
        
        # Add custom headers
        for header, value in email_msg.headers.items():
            msg[header] = value
        
        # Create message body
        if email_msg.text_content and email_msg.html_content:
            # Both text and HTML - create alternative container
            body_container = email.mime.multipart.MIMEMultipart('alternative')
            
            # Add text part
            text_part = email.mime.text.MIMEText(email_msg.text_content, 'plain', 'utf-8')
            body_container.attach(text_part)
            
            # Add HTML part
            html_part = email.mime.text.MIMEText(email_msg.html_content, 'html', 'utf-8')
            body_container.attach(html_part)
            
            msg.attach(body_container)
            
        elif email_msg.html_content:
            # HTML only
            html_part = email.mime.text.MIMEText(email_msg.html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
        elif email_msg.text_content:
            # Text only
            text_part = email.mime.text.MIMEText(email_msg.text_content, 'plain', 'utf-8')
            msg.attach(text_part)
        
        # Add attachments
        for attachment in email_msg.attachments:
            self._add_attachment_to_message(msg, attachment)
        
        return msg
    
    def _add_attachment_to_message(self, msg: email.mime.multipart.MIMEMultipart, attachment: EmailAttachment):
        """Add an attachment to the MIME message."""
        try:
            # Get attachment data
            if attachment.content:
                data = attachment.content
            elif attachment.filepath:
                with open(attachment.filepath, 'rb') as f:
                    data = f.read()
            else:
                raise SMTPClientError(f"No content or filepath for attachment {attachment.filename}")
            
            # Determine MIME type
            maintype, subtype = attachment.content_type.split('/', 1)
            
            if maintype == 'text':
                # Text attachment
                mime_attachment = email.mime.text.MIMEText(
                    data.decode('utf-8', errors='ignore'),
                    subtype,
                    'utf-8'
                )
            elif maintype == 'image':
                # Image attachment
                mime_attachment = email.mime.image.MIMEImage(data, subtype)
            else:
                # Binary attachment
                mime_attachment = email.mime.base.MIMEBase(maintype, subtype)
                mime_attachment.set_payload(data)
                email.encoders.encode_base64(mime_attachment)
            
            # Set attachment headers
            if attachment.is_inline and attachment.content_id:
                mime_attachment.add_header(
                    'Content-Disposition',
                    'inline',
                    filename=attachment.filename
                )
                mime_attachment.add_header('Content-ID', f'<{attachment.content_id}>')
            else:
                mime_attachment.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=attachment.filename
                )
            
            msg.attach(mime_attachment)
            
        except Exception as e:
            raise SMTPClientError(f"Failed to add attachment {attachment.filename}: {e}")
    
    def verify_connection(self) -> Tuple[bool, Optional[str]]:
        """
        Verify SMTP connection and authentication.
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if self.connect():
                self.disconnect()
                return True, None
            else:
                return False, "Connection failed"
        except Exception as e:
            return False, str(e)

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect() 