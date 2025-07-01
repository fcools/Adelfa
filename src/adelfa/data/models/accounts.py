"""
Account data models for Adelfa PIM suite.

Defines SQLAlchemy models for email, calendar, and contact accounts
with secure credential storage and multi-protocol support.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, 
    ForeignKey, Enum, JSON, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class AccountType(enum.Enum):
    """Enumeration for account types."""
    EMAIL = "email"
    CALENDAR = "calendar"
    CONTACTS = "contacts"
    COMBINED = "combined"  # Accounts that support multiple protocols


class EmailProtocol(enum.Enum):
    """Enumeration for email protocols."""
    IMAP = "imap"
    POP3 = "pop3"
    EXCHANGE_EWS = "exchange_ews"
    GMAIL_API = "gmail_api"


class SecurityType(enum.Enum):
    """Enumeration for connection security types."""
    NONE = "none"
    STARTTLS = "starttls"
    TLS_SSL = "tls_ssl"
    AUTO = "auto"


class AuthMethod(enum.Enum):
    """Enumeration for authentication methods."""
    PASSWORD = "password"
    OAUTH2 = "oauth2"
    XOAUTH2 = "xoauth2"
    NTLM = "ntlm"
    KERBEROS = "kerberos"


class AccountProvider(Base):
    """
    Account provider entity for common email/calendar/contact services.
    
    Stores configuration templates for popular providers like Gmail, Outlook, etc.
    """
    __tablename__ = "account_providers"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Provider configuration
    domains = Column(JSON)  # List of email domains this provider handles
    logo_url = Column(String(512))
    website_url = Column(String(512))
    
    # Email configuration
    imap_server = Column(String(255))
    imap_port = Column(Integer)
    imap_security = Column(Enum(SecurityType))
    
    pop3_server = Column(String(255))
    pop3_port = Column(Integer)
    pop3_security = Column(Enum(SecurityType))
    
    smtp_server = Column(String(255))
    smtp_port = Column(Integer)
    smtp_security = Column(Enum(SecurityType))
    
    # Calendar/Contacts configuration
    caldav_server = Column(String(255))
    carddav_server = Column(String(255))
    
    # Authentication
    auth_methods = Column(JSON)  # List of supported auth methods
    oauth2_config = Column(JSON)  # OAuth2 configuration if supported
    
    # Features
    supports_email = Column(Boolean, default=True)
    supports_calendar = Column(Boolean, default=False)
    supports_contacts = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<AccountProvider(name='{self.name}', display_name='{self.display_name}')>"


class Account(Base):
    """
    Account entity representing an email, calendar, or contact account.
    
    Supports multiple protocols and providers with secure credential storage.
    """
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True)
    provider_id = Column(Integer, ForeignKey("account_providers.id"))
    
    # Account identification
    name = Column(String(255), nullable=False)  # User-friendly name
    email_address = Column(String(320))  # Primary email address
    account_type = Column(Enum(AccountType), default=AccountType.EMAIL)
    
    # General settings
    is_enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    display_name = Column(String(255))  # Name to show in From field
    
    # Email configuration
    email_protocol = Column(Enum(EmailProtocol))
    
    # Incoming mail settings
    incoming_server = Column(String(255))
    incoming_port = Column(Integer)
    incoming_security = Column(Enum(SecurityType))
    incoming_username = Column(String(255))
    
    # Outgoing mail settings  
    outgoing_server = Column(String(255))
    outgoing_port = Column(Integer)
    outgoing_security = Column(Enum(SecurityType))
    outgoing_username = Column(String(255))
    outgoing_auth_required = Column(Boolean, default=True)
    
    # Calendar settings
    caldav_server = Column(String(512))
    caldav_username = Column(String(255))
    caldav_sync_enabled = Column(Boolean, default=False)
    
    # Contacts settings
    carddav_server = Column(String(512))
    carddav_username = Column(String(255))
    carddav_sync_enabled = Column(Boolean, default=False)
    
    # Authentication
    auth_method = Column(Enum(AuthMethod), default=AuthMethod.PASSWORD)
    
    # Secure credential storage (these reference keyring entries)
    incoming_password_key = Column(String(255))  # Keyring key for incoming password
    outgoing_password_key = Column(String(255))  # Keyring key for outgoing password
    caldav_password_key = Column(String(255))    # Keyring key for CalDAV password
    carddav_password_key = Column(String(255))   # Keyring key for CardDAV password
    oauth2_token_key = Column(String(255))       # Keyring key for OAuth2 tokens
    
    # Sync settings
    sync_frequency = Column(Integer, default=15)  # Minutes
    keep_messages_days = Column(Integer, default=30)  # Days to keep messages locally
    
    # Advanced settings
    advanced_settings = Column(JSON)  # Additional protocol-specific settings
    
    # Status tracking
    last_sync = Column(DateTime)
    last_error = Column(Text)
    connection_status = Column(String(50), default="not_tested")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    provider = relationship("AccountProvider")
    cached_folders = relationship("CachedFolder", back_populates="account", cascade="all, delete-orphan")
    cached_messages = relationship("CachedMessage", back_populates="account", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        UniqueConstraint("email_address", "account_type", name="uq_account_email_type"),
        Index("idx_account_enabled", "is_enabled"),
        Index("idx_account_default", "is_default"),
        Index("idx_account_email", "email_address"),
    )
    
    def get_keyring_service(self) -> str:
        """
        Get the keyring service name for this account.
        
        Returns:
            str: Service name for keyring storage.
        """
        return f"adelfa.account.{self.id}"
    
    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name='{self.name}', email='{self.email_address}')>"


class AccountConnectionTest(Base):
    """
    Account connection test results for tracking connectivity issues.
    """
    __tablename__ = "account_connection_tests"
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    
    # Test details
    test_type = Column(String(50), nullable=False)  # incoming, outgoing, caldav, carddav
    test_result = Column(String(50), nullable=False)  # success, failure, timeout
    error_message = Column(Text)
    response_time_ms = Column(Integer)
    
    # Test metadata
    tested_at = Column(DateTime, default=datetime.utcnow)
    client_info = Column(JSON)  # Details about the test environment
    
    # Relationships
    account = relationship("Account")
    
    def __repr__(self) -> str:
        return f"<AccountConnectionTest(account_id={self.account_id}, type='{self.test_type}', result='{self.test_result}')>" 