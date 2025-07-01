"""
Cache models for storing email data locally.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from .accounts import Base


class CachedFolder(Base):
    """Cached folder information for quick loading."""
    __tablename__ = 'cached_folders'
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    name = Column(String(255), nullable=False)
    delimiter = Column(String(10), default='/')
    flags = Column(Text)  # JSON string of flags
    exists = Column(Integer, default=0)
    recent = Column(Integer, default=0)
    unseen = Column(Integer, default=0)
    uidvalidity = Column(Integer, default=0)
    uidnext = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to account
    account = relationship("Account", back_populates="cached_folders")


class CachedMessage(Base):
    """Cached message headers for quick loading."""
    __tablename__ = 'cached_messages'
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    folder_name = Column(String(255), nullable=False)
    uid = Column(Integer, nullable=False)
    message_id = Column(String(255))
    subject = Column(Text)
    from_addr = Column(Text)
    to_addrs = Column(Text)  # JSON string
    cc_addrs = Column(Text)  # JSON string
    date = Column(DateTime)
    flags = Column(Text)  # JSON string of flags
    size = Column(Integer, default=0)
    has_attachments = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to account
    account = relationship("Account", back_populates="cached_messages")
    
    # Unique constraint on account_id, folder_name, uid
    __table_args__ = (
        {'sqlite_autoincrement': True},
    ) 