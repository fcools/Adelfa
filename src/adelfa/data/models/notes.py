"""
Notes data models for Adelfa PIM suite.

Defines SQLAlchemy models for notes, notebooks, and note organization.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, 
    ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Notebook(Base):
    """
    Notebook entity for organizing notes.
    
    Represents a collection or category of notes.
    """
    __tablename__ = "notebooks"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(7), default="#f39c12")  # Hex color code
    is_default = Column(Boolean, default=False)
    is_visible = Column(Boolean, default=True)
    
    # Organization
    parent_notebook_id = Column(Integer, ForeignKey("notebooks.id"))
    sort_order = Column(Integer, default=0)
    
    # Server synchronization fields (for future cloud sync)
    server_url = Column(String(512))
    server_id = Column(String(255))
    last_sync = Column(DateTime)
    sync_token = Column(String(512))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    notes = relationship("Note", back_populates="notebook", cascade="all, delete-orphan")
    child_notebooks = relationship("Notebook", remote_side=[id], cascade="all, delete-orphan")
    parent_notebook = relationship("Notebook", remote_side=[parent_notebook_id])
    
    def __repr__(self) -> str:
        return f"<Notebook(id={self.id}, name='{self.name}')>"


class Note(Base):
    """
    Note entity representing a text note or memo.
    
    Supports rich text content and various organizational features.
    """
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id"), nullable=False)
    
    # Basic note information
    title = Column(String(512), nullable=False)
    content = Column(Text)  # Rich text content (HTML)
    plain_text_content = Column(Text)  # Plain text for searching
    
    # Organization and metadata
    tags = Column(JSON)  # List of tag strings
    is_pinned = Column(Boolean, default=False)
    is_favorite = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)  # Soft delete
    
    # Security
    is_encrypted = Column(Boolean, default=False)
    encryption_key_id = Column(String(255))  # Reference to encryption key
    
    # Reminders and scheduling
    has_reminder = Column(Boolean, default=False)
    reminder_date = Column(DateTime)
    
    # Sharing and collaboration (for future features)
    is_shared = Column(Boolean, default=False)
    share_permissions = Column(JSON)  # List of user permissions
    
    # Version control (for tracking changes)
    version = Column(Integer, default=1)
    previous_version_id = Column(Integer, ForeignKey("notes.id"))
    
    # Server synchronization
    server_id = Column(String(255))
    etag = Column(String(255))
    last_modified = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accessed_at = Column(DateTime, default=datetime.utcnow)  # Last viewed
    
    # Relationships
    notebook = relationship("Notebook", back_populates="notes")
    attachments = relationship("NoteAttachment", back_populates="note", cascade="all, delete-orphan")
    version_history = relationship("Note", remote_side=[id])
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_note_notebook_title", "notebook_id", "title"),
        Index("idx_note_tags", "tags"),
        Index("idx_note_pinned", "is_pinned"),
        Index("idx_note_created", "created_at"),
        Index("idx_note_updated", "updated_at"),
        Index("idx_note_server_id", "server_id"),
        # Full-text search index on content (database-specific)
    )
    
    def get_word_count(self) -> int:
        """
        Get the word count of the note content.
        
        Returns:
            int: Number of words in the note.
        """
        if not self.plain_text_content:
            return 0
        return len(self.plain_text_content.split())
    
    def get_character_count(self) -> int:
        """
        Get the character count of the note content.
        
        Returns:
            int: Number of characters in the note.
        """
        if not self.plain_text_content:
            return 0
        return len(self.plain_text_content)
    
    def add_tag(self, tag: str) -> None:
        """
        Add a tag to the note.
        
        Args:
            tag: Tag to add.
        """
        if not self.tags:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """
        Remove a tag from the note.
        
        Args:
            tag: Tag to remove.
        """
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
    
    def __repr__(self) -> str:
        return f"<Note(id={self.id}, title='{self.title}')>"


class NoteAttachment(Base):
    """
    Note attachment entity for files attached to notes.
    
    Represents files, images, or other attachments linked to a note.
    """
    __tablename__ = "note_attachments"
    
    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=False)
    
    # File information
    filename = Column(String(512), nullable=False)
    original_filename = Column(String(512))
    file_path = Column(String(1024))  # Path to stored file
    file_size = Column(Integer)  # Size in bytes
    mime_type = Column(String(255))
    
    # File metadata
    is_inline = Column(Boolean, default=False)  # Embedded in note content
    width = Column(Integer)  # For images
    height = Column(Integer)  # For images
    
    # Thumbnails and previews
    thumbnail_path = Column(String(1024))
    preview_path = Column(String(1024))
    
    # Server synchronization
    server_id = Column(String(255))
    etag = Column(String(255))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    note = relationship("Note", back_populates="attachments")
    
    def __repr__(self) -> str:
        return f"<NoteAttachment(id={self.id}, filename='{self.filename}')>"


class NoteTag(Base):
    """
    Note tag entity for tag management and statistics.
    
    Tracks usage statistics and metadata for tags.
    """
    __tablename__ = "note_tags"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    color = Column(String(7))  # Hex color code
    description = Column(Text)
    
    # Usage statistics
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<NoteTag(name='{self.name}', usage_count={self.usage_count})>" 