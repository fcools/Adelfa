"""
Data models for Adelfa PIM suite.
"""

from .accounts import Account, AccountProvider, AccountConnectionTest
from .calendar import Calendar, Event, Attendee, Reminder
from .contacts import Contact, ContactGroup, ContactEmail, ContactPhone, ContactAddress, ContactGroupMembership
from .notes import Note, Notebook, NoteAttachment, NoteTag
from .tasks import Task, TaskList, TaskPriority
from .cache import CachedFolder, CachedMessage

# Base class for all models
from .accounts import Base

__all__ = [
    'Base',
    'Account', 
    'AccountProvider',
    'AccountConnectionTest',
    'Calendar',
    'Event',
    'Attendee',
    'Reminder', 
    'Contact',
    'ContactGroup',
    'ContactEmail',
    'ContactPhone',
    'ContactAddress',
    'ContactGroupMembership',
    'Note',
    'Notebook',
    'NoteAttachment',
    'NoteTag',
    'Task',
    'TaskList',
    'TaskPriority',
    'CachedFolder',
    'CachedMessage',
]
