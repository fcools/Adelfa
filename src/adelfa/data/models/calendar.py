"""
Calendar data models for Adelfa PIM suite.

Defines SQLAlchemy models for calendar events, recurring patterns,
reminders, and calendar metadata.
"""

from datetime import datetime, date, time
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Time, Text, Boolean, 
    ForeignKey, Enum, JSON, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class RecurrenceType(enum.Enum):
    """Enumeration for recurrence patterns."""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class EventStatus(enum.Enum):
    """Enumeration for event status."""
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class AttendeeStatus(enum.Enum):
    """Enumeration for attendee response status."""
    NEEDS_ACTION = "needs-action"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    DELEGATED = "delegated"


class Calendar(Base):
    """
    Calendar entity representing a calendar collection.
    
    A calendar is a collection of events. Users can have multiple
    calendars (personal, work, shared, etc.).
    """
    __tablename__ = "calendars"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(7), default="#3788d8")  # Hex color code
    is_default = Column(Boolean, default=False)
    is_visible = Column(Boolean, default=True)
    is_read_only = Column(Boolean, default=False)
    
    # Server synchronization fields
    server_url = Column(String(512))  # CalDAV server URL
    server_id = Column(String(255))   # Server-side calendar ID
    last_sync = Column(DateTime)
    sync_token = Column(String(512))  # ETag or sync token
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    events = relationship("Event", back_populates="calendar", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Calendar(id={self.id}, name='{self.name}')>"


class Event(Base):
    """
    Calendar event entity.
    
    Represents a calendar event with all standard properties
    compatible with iCalendar (RFC 5545) specification.
    """
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True)
    calendar_id = Column(Integer, ForeignKey("calendars.id"), nullable=False)
    
    # Basic event information
    title = Column(String(512), nullable=False)
    description = Column(Text)
    location = Column(String(512))
    
    # Timing
    start_date = Column(Date)
    start_time = Column(Time)
    end_date = Column(Date)
    end_time = Column(Time)
    is_all_day = Column(Boolean, default=False)
    timezone = Column(String(50), default="UTC")
    
    # Recurrence
    recurrence_type = Column(Enum(RecurrenceType), default=RecurrenceType.NONE)
    recurrence_rule = Column(String(512))  # RRULE string
    recurrence_exceptions = Column(JSON)   # List of exception dates
    recurrence_parent_id = Column(Integer, ForeignKey("events.id"))
    
    # Status and visibility
    status = Column(Enum(EventStatus), default=EventStatus.CONFIRMED)
    is_private = Column(Boolean, default=False)
    is_busy = Column(Boolean, default=True)  # For free/busy calculations
    
    # Reminders and notifications
    has_reminder = Column(Boolean, default=False)
    reminder_minutes = Column(Integer)  # Minutes before event
    
    # Server synchronization
    server_id = Column(String(255))  # UID from iCalendar
    etag = Column(String(255))       # ETag for optimistic locking
    last_modified = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    calendar = relationship("Calendar", back_populates="events")
    attendees = relationship("Attendee", back_populates="event", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="event", cascade="all, delete-orphan")
    recurrence_children = relationship("Event", remote_side=[id])
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_event_calendar_dates", "calendar_id", "start_date", "end_date"),
        Index("idx_event_server_id", "server_id"),
        Index("idx_event_recurrence", "recurrence_parent_id"),
    )
    
    def __repr__(self) -> str:
        return f"<Event(id={self.id}, title='{self.title}', start='{self.start_date}')>"


class Attendee(Base):
    """
    Event attendee entity.
    
    Represents a person invited to a calendar event.
    """
    __tablename__ = "attendees"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    
    # Attendee information
    name = Column(String(255))
    email = Column(String(320), nullable=False)  # RFC 5322 max length
    role = Column(String(50), default="REQ-PARTICIPANT")  # CHAIR, REQ-PARTICIPANT, OPT-PARTICIPANT
    status = Column(Enum(AttendeeStatus), default=AttendeeStatus.NEEDS_ACTION)
    
    # RSVP and delegation
    rsvp_required = Column(Boolean, default=True)
    delegated_to = Column(String(320))
    delegated_from = Column(String(320))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("Event", back_populates="attendees")
    
    def __repr__(self) -> str:
        return f"<Attendee(email='{self.email}', status='{self.status.value}')>"


class Reminder(Base):
    """
    Event reminder entity.
    
    Represents a reminder/alarm for a calendar event.
    """
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    
    # Reminder configuration
    minutes_before = Column(Integer, nullable=False)  # Minutes before event
    reminder_type = Column(String(20), default="popup")  # popup, email, sound
    message = Column(Text)
    
    # Execution tracking
    is_triggered = Column(Boolean, default=False)
    triggered_at = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("Event", back_populates="reminders")
    
    def __repr__(self) -> str:
        return f"<Reminder(event_id={self.event_id}, minutes_before={self.minutes_before})>" 