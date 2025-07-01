"""
Tasks data models for Adelfa PIM suite.

Defines SQLAlchemy models for tasks, task lists, and task management.
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Text, Boolean, 
    ForeignKey, Enum, JSON, Index, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class TaskPriority(enum.Enum):
    """Enumeration for task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(enum.Enum):
    """Enumeration for task status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAITING = "waiting"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class TaskList(Base):
    """
    Task list entity for organizing tasks.
    
    Represents a list or project containing multiple tasks.
    """
    __tablename__ = "task_lists"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(7), default="#3788d8")  # Hex color code
    is_default = Column(Boolean, default=False)
    is_visible = Column(Boolean, default=True)
    
    # Server synchronization fields
    server_url = Column(String(512))  # CalDAV server URL (for task lists)
    server_id = Column(String(255))   # Server-side task list ID
    last_sync = Column(DateTime)
    sync_token = Column(String(512))  # ETag or sync token
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks = relationship("Task", back_populates="task_list", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<TaskList(id={self.id}, name='{self.name}')>"


class Task(Base):
    """
    Task entity representing a to-do item.
    
    Compatible with iCalendar VTODO specification.
    """
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True)
    task_list_id = Column(Integer, ForeignKey("task_lists.id"), nullable=False)
    
    # Basic task information
    title = Column(String(512), nullable=False)
    description = Column(Text)
    
    # Task scheduling
    start_date = Column(Date)
    due_date = Column(Date)
    completed_date = Column(Date)
    
    # Task properties
    priority = Column(Enum(TaskPriority), default=TaskPriority.NORMAL)
    status = Column(Enum(TaskStatus), default=TaskStatus.NOT_STARTED)
    percent_complete = Column(Integer, default=0)  # 0-100
    
    # Organization
    categories = Column(JSON)  # List of category strings
    tags = Column(JSON)        # List of tag strings
    
    # Relationships
    parent_task_id = Column(Integer, ForeignKey("tasks.id"))
    
    # Reminders
    has_reminder = Column(Boolean, default=False)
    reminder_date = Column(DateTime)
    
    # Time tracking
    estimated_hours = Column(Float)  # Estimated time to complete
    actual_hours = Column(Float)     # Actual time spent
    
    # Server synchronization
    server_id = Column(String(255))  # UID from iCalendar
    etag = Column(String(255))       # ETag for optimistic locking
    last_modified = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    task_list = relationship("TaskList", back_populates="tasks")
    subtasks = relationship("Task", remote_side=[id], cascade="all, delete-orphan")
    parent_task = relationship("Task", remote_side=[parent_task_id])
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_task_list_status", "task_list_id", "status"),
        Index("idx_task_due_date", "due_date"),
        Index("idx_task_priority", "priority"),
        Index("idx_task_server_id", "server_id"),
    )
    
    def is_overdue(self) -> bool:
        """
        Check if the task is overdue.
        
        Returns:
            bool: True if task is overdue, False otherwise.
        """
        if not self.due_date or self.status == TaskStatus.COMPLETED:
            return False
        return self.due_date < date.today()
    
    def get_completion_percentage(self) -> int:
        """
        Get the completion percentage, considering subtasks.
        
        Returns:
            int: Completion percentage (0-100).
        """
        if self.status == TaskStatus.COMPLETED:
            return 100
        
        if not self.subtasks:
            return self.percent_complete
        
        # Calculate based on subtask completion
        total_subtasks = len(self.subtasks)
        completed_subtasks = sum(1 for subtask in self.subtasks if subtask.status == TaskStatus.COMPLETED)
        
        return int((completed_subtasks / total_subtasks) * 100) if total_subtasks > 0 else 0
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status.value}')>" 