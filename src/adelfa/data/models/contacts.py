"""
Contacts data models for Adelfa PIM suite.

Defines SQLAlchemy models for contacts, groups, addresses,
phone numbers, and other contact information.
"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Text, Boolean, 
    ForeignKey, Enum, JSON, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class PhoneType(enum.Enum):
    """Enumeration for phone number types."""
    HOME = "home"
    WORK = "work"
    MOBILE = "mobile"
    FAX = "fax"
    PAGER = "pager"
    OTHER = "other"


class EmailType(enum.Enum):
    """Enumeration for email address types."""
    HOME = "home"
    WORK = "work"
    OTHER = "other"


class AddressType(enum.Enum):
    """Enumeration for address types."""
    HOME = "home"
    WORK = "work"
    OTHER = "other"


class ContactGroup(Base):
    """
    Contact group entity for organizing contacts.
    
    Represents a group or category of contacts (e.g., Family, Work, Friends).
    """
    __tablename__ = "contact_groups"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(7), default="#808080")  # Hex color code
    
    # Server synchronization fields
    server_url = Column(String(512))  # CardDAV server URL
    server_id = Column(String(255))   # Server-side group ID
    last_sync = Column(DateTime)
    sync_token = Column(String(512))  # ETag or sync token
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<ContactGroup(id={self.id}, name='{self.name}')>"


class Contact(Base):
    """
    Contact entity representing a person or organization.
    
    Compatible with vCard 4.0 specification (RFC 6350).
    """
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True)
    
    # Basic information
    first_name = Column(String(255))
    last_name = Column(String(255))
    middle_name = Column(String(255))
    name_prefix = Column(String(50))     # Mr., Mrs., Dr., etc.
    name_suffix = Column(String(50))     # Jr., Sr., III, etc.
    display_name = Column(String(512))   # Formatted full name
    nickname = Column(String(255))
    
    # Organization information
    company = Column(String(255))
    department = Column(String(255))
    job_title = Column(String(255))
    
    # Personal information
    birthday = Column(Date)
    anniversary = Column(Date)
    spouse_name = Column(String(255))
    
    # Notes and categories
    notes = Column(Text)
    categories = Column(JSON)  # List of category strings
    
    # Photo/avatar
    photo_url = Column(String(512))
    photo_data = Column(Text)  # Base64 encoded image data
    
    # Server synchronization
    server_id = Column(String(255))  # UID from vCard
    etag = Column(String(255))       # ETag for optimistic locking
    last_modified = Column(DateTime)
    server_url = Column(String(512))  # CardDAV server URL
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    emails = relationship("ContactEmail", back_populates="contact", cascade="all, delete-orphan")
    phones = relationship("ContactPhone", back_populates="contact", cascade="all, delete-orphan")
    addresses = relationship("ContactAddress", back_populates="contact", cascade="all, delete-orphan")
    group_memberships = relationship("ContactGroupMembership", back_populates="contact", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_contact_name", "last_name", "first_name"),
        Index("idx_contact_company", "company"),
        Index("idx_contact_server_id", "server_id"),
    )
    
    def get_full_name(self) -> str:
        """
        Get the formatted full name of the contact.
        
        Returns:
            str: Formatted full name.
        """
        if self.display_name:
            return self.display_name
        
        parts = []
        if self.name_prefix:
            parts.append(self.name_prefix)
        if self.first_name:
            parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        if self.last_name:
            parts.append(self.last_name)
        if self.name_suffix:
            parts.append(self.name_suffix)
        
        return " ".join(parts) if parts else "Unknown"
    
    def __repr__(self) -> str:
        return f"<Contact(id={self.id}, name='{self.get_full_name()}')>"


class ContactEmail(Base):
    """
    Contact email address entity.
    
    Represents an email address associated with a contact.
    """
    __tablename__ = "contact_emails"
    
    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    
    email = Column(String(320), nullable=False)  # RFC 5322 max length
    email_type = Column(Enum(EmailType), default=EmailType.HOME)
    is_primary = Column(Boolean, default=False)
    label = Column(String(100))  # Custom label
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contact = relationship("Contact", back_populates="emails")
    
    def __repr__(self) -> str:
        return f"<ContactEmail(email='{self.email}', type='{self.email_type.value}')>"


class ContactPhone(Base):
    """
    Contact phone number entity.
    
    Represents a phone number associated with a contact.
    """
    __tablename__ = "contact_phones"
    
    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    
    number = Column(String(50), nullable=False)
    phone_type = Column(Enum(PhoneType), default=PhoneType.HOME)
    is_primary = Column(Boolean, default=False)
    label = Column(String(100))  # Custom label
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contact = relationship("Contact", back_populates="phones")
    
    def __repr__(self) -> str:
        return f"<ContactPhone(number='{self.number}', type='{self.phone_type.value}')>"


class ContactAddress(Base):
    """
    Contact address entity.
    
    Represents a postal address associated with a contact.
    """
    __tablename__ = "contact_addresses"
    
    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    
    # Address components
    street = Column(String(512))
    city = Column(String(255))
    state = Column(String(255))
    postal_code = Column(String(50))
    country = Column(String(255))
    
    address_type = Column(Enum(AddressType), default=AddressType.HOME)
    is_primary = Column(Boolean, default=False)
    label = Column(String(100))  # Custom label
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contact = relationship("Contact", back_populates="addresses")
    
    def get_formatted_address(self) -> str:
        """
        Get the formatted address string.
        
        Returns:
            str: Formatted address.
        """
        parts = []
        if self.street:
            parts.append(self.street)
        
        city_line = []
        if self.city:
            city_line.append(self.city)
        if self.state:
            city_line.append(self.state)
        if self.postal_code:
            city_line.append(self.postal_code)
        if city_line:
            parts.append(", ".join(city_line))
        
        if self.country:
            parts.append(self.country)
        
        return "\n".join(parts)
    
    def __repr__(self) -> str:
        return f"<ContactAddress(city='{self.city}', type='{self.address_type.value}')>"


class ContactGroupMembership(Base):
    """
    Contact group membership entity.
    
    Represents the many-to-many relationship between contacts and groups.
    """
    __tablename__ = "contact_group_memberships"
    
    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("contact_groups.id"), nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    contact = relationship("Contact", back_populates="group_memberships")
    group = relationship("ContactGroup")
    
    # Ensure unique contact-group combinations
    __table_args__ = (
        UniqueConstraint("contact_id", "group_id", name="uq_contact_group"),
    )
    
    def __repr__(self) -> str:
        return f"<ContactGroupMembership(contact_id={self.contact_id}, group_id={self.group_id})>" 