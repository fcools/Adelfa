"""
Main email view for Adelfa PIM suite.

Provides Outlook-style email interface with folder tree, message list,
message preview, and email composition functionality.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QTextEdit, QToolBar, QComboBox, QLineEdit,
    QPushButton, QLabel, QFrame, QHeaderView, QAbstractItemView, QMenu,
    QMessageBox, QProgressBar, QStatusBar, QCheckBox, QDateEdit, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QDate
from PyQt6.QtGui import QIcon, QFont, QAction, QPixmap, QKeySequence
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import html
import re
import locale

from ...core.email.email_manager import EmailManager, EmailManagerError
from ...core.email.imap_client import EmailMessage, FolderInfo
from ...core.email.smtp_client import OutgoingEmail, EmailAddress
from ...data.models.accounts import Account
from ...utils.i18n import _
from .email_composer import EmailComposer


class ConversationThread:
    """Represents a conversation thread of related emails."""
    
    def __init__(self, subject: str):
        self.subject = subject
        self.normalized_subject = self._normalize_subject(subject)
        self.messages: List[EmailMessage] = []
        self.latest_date = None
        self.has_unread = False
        self.message_count = 0
    
    def add_message(self, message: EmailMessage):
        """Add a message to this conversation thread."""
        self.messages.append(message)
        self.message_count = len(self.messages)
        
        # Update latest date
        if not self.latest_date or message.headers.date > self.latest_date:
            self.latest_date = message.headers.date
        
        # Check for unread messages
        if not message.is_read:
            self.has_unread = True
    
    def get_latest_message(self) -> Optional[EmailMessage]:
        """Get the most recent message in the thread."""
        if not self.messages:
            return None
        return max(self.messages, key=lambda m: m.headers.date)
    
    def get_participants(self) -> List[str]:
        """Get all unique participants in the conversation (display names only)."""
        participants = set()
        for message in self.messages:
            # Extract display name from from_addr
            from_name = self._extract_display_name(message.headers.from_addr)
            participants.add(from_name)
            
            if hasattr(message.headers, 'to_addrs') and message.headers.to_addrs:
                for addr in message.headers.to_addrs:
                    to_name = self._extract_display_name(addr.strip())
                    participants.add(to_name)
            elif hasattr(message.headers, 'to') and message.headers.to:
                for addr in message.headers.to.split(','):
                    to_name = self._extract_display_name(addr.strip())
                    participants.add(to_name)
        return list(participants)
    
    def _extract_display_name(self, email_addr: str) -> str:
        """
        Extract display name from email address.
        
        Examples:
        - "John Doe <john@example.com>" → "John Doe"
        - "john@example.com" → "john@example.com"
        - "John Doe" → "John Doe"
        """
        if not email_addr:
            return ""
        
        # Pattern to match "Name <email@domain.com>" format
        match = re.match(r'^(.+?)\s*<[^>]+>$', email_addr.strip())
        if match:
            name = match.group(1).strip()
            # Remove surrounding quotes if present
            if (name.startswith('"') and name.endswith('"')) or \
               (name.startswith("'") and name.endswith("'")):
                name = name[1:-1]
            return name if name else email_addr
        
        # If no match, return the original string (likely just an email or name)
        return email_addr.strip()
    
    @staticmethod
    def _normalize_subject(subject: str) -> str:
        """Normalize subject for threading (remove Re:, Fwd:, etc.)."""
        if not subject:
            return ""
        
        # Remove common prefixes
        prefixes = ['re:', 'fwd:', 'fw:', 'forward:', 'reply:']
        normalized = subject.lower().strip()
        
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        return normalized
    
    def matches_subject(self, subject: str) -> bool:
        """Check if a subject belongs to this conversation thread."""
        return self._normalize_subject(subject) == self.normalized_subject


class ThreadedMessageListWidget(QTableWidget):
    """Message list widget with conversation threading support."""
    
    message_selected = pyqtSignal(int)  # uid
    message_double_clicked = pyqtSignal(int)  # uid
    thread_expanded = pyqtSignal(str)  # thread_id
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.threads: Dict[str, ConversationThread] = {}
        self.show_threading = True
        self.expanded_threads: set = set()
        
        # For column width persistence
        self.config = None  # Will be set by EmailView
    
    def setup_ui(self):
        """Setup the threaded message list UI."""
        # Configure table
        self.setColumnCount(7)
        # Reordered columns: Attachment, Importance, Threading, From, Subject, Date, Size
        self.setHorizontalHeaderLabels([
            "📎", "❗", "⏵", "From", "Subject", "Date", "Size"
        ])
        
        # Configure selection and behavior
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        
        # Make table non-editable
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Remove grid lines
        self.setShowGrid(False)
        
        # Remove row numbering
        self.verticalHeader().setVisible(False)
        
        # Configure headers - make columns adjustable with Subject stretching
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionsClickable(True)  # Allow sorting by clicking headers
        header.setSectionsMovable(False)   # Prevent column reordering
        
        # Set column resize modes - make most columns interactive (resizable)
        # but keep icon columns fixed for consistency
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)        # Attachment (icon)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)        # Importance (icon)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)        # Threading (icon, smaller)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  # From (resizable)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)      # Subject (stretches to fill)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)  # Date (resizable)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)  # Size (resizable)
        
        # Set initial column widths (will be overridden by saved settings)
        self.setColumnWidth(0, 25)   # Attachment column (fixed)
        self.setColumnWidth(1, 25)   # Importance column (fixed)
        self.setColumnWidth(2, 20)   # Threading column (fixed, smaller and less intrusive)
        self.setColumnWidth(3, 150)  # From column (initial width, user can resize)
        # Subject column will stretch automatically
        self.setColumnWidth(5, 120)  # Date column (initial width, user can resize)
        self.setColumnWidth(6, 80)   # Size column (initial width, user can resize)
        
        # Add styling to match folder tree font size and make threading less intrusive
        self.setStyleSheet("""
            QTableWidget {
                font-size: 13px;
                gridline-color: transparent;
                outline: none;
                border: none;
            }
            QTableWidget::item {
                padding: 4px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QTableWidget::item:hover {
                background-color: #e5f3ff;
            }
        """)
        
        # Connect signals
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_double_clicked)
        self.itemClicked.connect(self._on_item_clicked)
        
        # Connect to column resize signal for persistence
        header.sectionResized.connect(self._on_column_resized)
    
    def set_config(self, config):
        """Set the app config for column width persistence."""
        self.config = config
        self._load_column_widths()
    
    def _load_column_widths(self):
        """Load saved column widths from config."""
        if not self.config:
            return
            
        saved_widths = self.config.ui.email_column_widths
        for column, width in saved_widths.items():
            if 0 <= column < self.columnCount():
                self.setColumnWidth(column, width)
    
    def _save_column_widths(self):
        """Save current column widths to config."""
        if not self.config:
            return
            
        # Save widths for resizable columns only (not stretch column)
        widths = {}
        for column in range(self.columnCount()):
            if column != 4:  # Skip subject column (stretch)
                widths[column] = self.columnWidth(column)
        
        self.config.ui.email_column_widths = widths
        self.config.save()
    
    def _on_column_resized(self, logical_index: int, old_size: int, new_size: int):
        """Handle column resize event and save to config."""
        # Only save for resizable columns (not fixed or stretch)
        if logical_index in [3, 5, 6]:  # From, Date, Size columns
            self._save_column_widths()
    
    def _extract_display_name(self, email_addr: str) -> str:
        """
        Extract display name from email address.
        
        Examples:
        - "John Doe <john@example.com>" → "John Doe"
        - "john@example.com" → "john@example.com"
        - "John Doe" → "John Doe"
        """
        if not email_addr:
            return ""
        
        # Pattern to match "Name <email@domain.com>" format
        match = re.match(r'^(.+?)\s*<[^>]+>$', email_addr.strip())
        if match:
            name = match.group(1).strip()
            # Remove surrounding quotes if present
            if (name.startswith('"') and name.endswith('"')) or \
               (name.startswith("'") and name.endswith("'")):
                name = name[1:-1]
            return name if name else email_addr
        
        # If no match, return the original string (likely just an email or name)
        return email_addr.strip()
    
    def _format_date_system_locale(self, date_obj: datetime) -> str:
        """
        Format date using system locale.
        Falls back to ISO format if locale formatting fails.
        """
        try:
            # Try to use system locale for date formatting
            return date_obj.strftime("%x %X")  # %x = locale date, %X = locale time
        except (ValueError, AttributeError):
            # Fallback to a readable format if locale formatting fails
            return date_obj.strftime("%Y-%m-%d %H:%M")

    def toggle_threading(self):
        """Toggle conversation threading on/off."""
        self.show_threading = not self.show_threading
        self._rebuild_display()
    
    def add_messages(self, messages: List[EmailMessage]):
        """Add multiple messages and organize them into threads."""
        # Clear existing data
        self.clear_messages()
        
        if self.show_threading:
            # Group messages into conversation threads
            self._build_threads(messages)
            self._display_threads()
        else:
            # Display messages individually
            for message in sorted(messages, key=lambda m: m.headers.date, reverse=True):
                self._add_single_message(message)
    
    def _build_threads(self, messages: List[EmailMessage]):
        """Build conversation threads from messages."""
        self.threads.clear()
        
        for message in messages:
            subject = message.headers.subject or "(No Subject)"
            thread_found = False
            
            # Look for existing thread with matching subject
            for thread_id, thread in self.threads.items():
                if thread.matches_subject(subject):
                    thread.add_message(message)
                    thread_found = True
                    break
            
            # Create new thread if no match found
            if not thread_found:
                thread_id = f"thread_{len(self.threads)}"
                thread = ConversationThread(subject)
                thread.add_message(message)
                self.threads[thread_id] = thread
    
    def _display_threads(self):
        """Display conversation threads in the table."""
        # Sort threads by latest message date
        sorted_threads = sorted(
            self.threads.items(),
            key=lambda item: item[1].latest_date or datetime.min,
            reverse=True
        )
        
        for thread_id, thread in sorted_threads:
            if thread.message_count == 1:
                # For single messages, just show the message without thread header
                # Use the thread_message display to maintain threading context
                self._add_thread_message(thread.messages[0], thread_id, single_message=True)
            else:
                # For multi-message threads, show thread header
                self._add_thread_header(thread_id, thread)
                
                # Show thread messages if expanded
                if thread_id in self.expanded_threads:
                    # Sort messages in thread by date
                    sorted_messages = sorted(thread.messages, key=lambda m: m.headers.date)
                    for message in sorted_messages:
                        self._add_thread_message(message, thread_id)
    
    def _add_thread_header(self, thread_id: str, thread: ConversationThread):
        """Add a thread header row."""
        row = self.rowCount()
        self.insertRow(row)
        
        # Attachments indicator (column 0)
        has_attachments = any(msg.attachments for msg in thread.messages)
        attachment_item = QTableWidgetItem("📎" if has_attachments else "")
        attachment_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 0, attachment_item)
        
        # Importance indicator (column 1)
        has_flagged = any(getattr(msg, 'is_flagged', False) for msg in thread.messages)
        importance_item = QTableWidgetItem("★" if has_flagged else "")
        importance_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 1, importance_item)
        
        # Threading indicator (column 2, less intrusive)
        expand_icon = "▼" if thread_id in self.expanded_threads else "▶"  # Standard: right when collapsed, down when expanded
        threading_item = QTableWidgetItem(expand_icon)
        threading_item.setData(Qt.ItemDataRole.UserRole, {'type': 'thread_header', 'thread_id': thread_id})
        threading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        # Make font smaller and less bold for less intrusive appearance
        font = threading_item.font()
        font.setPointSize(font.pointSize() - 1)
        threading_item.setFont(font)
        self.setItem(row, 2, threading_item)
        
        # Participants (from addresses)
        participants = thread.get_participants()[:3]  # Show first 3 participants
        participants_text = ", ".join(participants)
        if len(thread.get_participants()) > 3:
            participants_text += "..."
        
        from_item = QTableWidgetItem(participants_text)
        if thread.has_unread:
            font = from_item.font()
            font.setBold(True)
            from_item.setFont(font)
        self.setItem(row, 3, from_item)
        
        # Subject with message count
        subject_text = f"{thread.subject} ({thread.message_count})"
        subject_item = QTableWidgetItem(subject_text)
        if thread.has_unread:
            font = subject_item.font()
            font.setBold(True)
            subject_item.setFont(font)
        # Make thread headers slightly different style
        subject_item.setBackground(self.palette().alternateBase())
        self.setItem(row, 4, subject_item)
        
        # Latest date
        date_str = self._format_date_system_locale(thread.latest_date)
        date_item = QTableWidgetItem(date_str)
        if thread.has_unread:
            font = date_item.font()
            font.setBold(True)
            date_item.setFont(font)
        self.setItem(row, 5, date_item)
        
        # Total size (approximate)
        total_size = sum(msg.size for msg in thread.messages)
        size_item = QTableWidgetItem(self._format_size(total_size))
        self.setItem(row, 6, size_item)
    
    def _add_thread_message(self, message: EmailMessage, thread_id: str, single_message: bool = False):
        """Add an individual message within a thread."""
        row = self.rowCount()
        self.insertRow(row)
        
        # Attachments indicator (column 0)
        attachment_item = QTableWidgetItem("📎" if message.attachments else "")
        attachment_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 0, attachment_item)
        
        # Importance indicator (column 1)
        importance_icon = "★" if getattr(message, 'is_flagged', False) else ""
        importance_item = QTableWidgetItem(importance_icon)
        importance_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 1, importance_item)
        
        # Threading indicator (column 2, less intrusive)
        if single_message:
            # For single messages, show empty threading column
            threading_icon = ""
        else:
            # For thread messages, show indentation with subtle indicator
            threading_icon = "  └"  # Indented with tree-like connector
        
        threading_item = QTableWidgetItem(threading_icon)
        threading_item.setData(Qt.ItemDataRole.UserRole, {
            'type': 'thread_message', 
            'thread_id': thread_id, 
            'message': message
        })
        # For thread messages, align left to show indentation clearly
        if single_message:
            threading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            threading_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            # Make font smaller for less intrusive appearance
            font = threading_item.font()
            font.setPointSize(max(8, font.pointSize() - 2))  # Smaller font, minimum 8pt
            threading_item.setFont(font)
        
        self.setItem(row, 2, threading_item)
        
        # From (display name only)
        from_display_name = self._extract_display_name(message.headers.from_addr)
        # Add indentation for thread messages to show hierarchy
        if not single_message:
            from_display_name = "    " + from_display_name  # Indent thread messages
        
        from_item = QTableWidgetItem(from_display_name)
        if not message.is_read:
            font = from_item.font()
            font.setBold(True)
            from_item.setFont(font)
        self.setItem(row, 3, from_item)
        
        # Subject
        subject_text = message.headers.subject or "(No Subject)"
        # Add indentation for thread messages to show hierarchy
        if not single_message:
            subject_text = "    " + subject_text  # Indent thread messages
        
        subject_item = QTableWidgetItem(subject_text)
        if not message.is_read:
            font = subject_item.font()
            font.setBold(True)
            subject_item.setFont(font)
        self.setItem(row, 4, subject_item)
        
        # Date (system locale format)
        date_str = self._format_date_system_locale(message.headers.date)
        date_item = QTableWidgetItem(date_str)
        if not message.is_read:
            font = date_item.font()
            font.setBold(True)
            date_item.setFont(font)
        self.setItem(row, 5, date_item)
        
        # Size
        size_str = self._format_size(message.size)
        size_item = QTableWidgetItem(size_str)
        self.setItem(row, 6, size_item)
    
    def _add_single_message(self, message: EmailMessage):
        """Add a single message (non-threaded view)."""
        row = self.rowCount()
        self.insertRow(row)
        
        # Attachments indicator (now column 0)
        attachment_item = QTableWidgetItem("📎" if message.attachments else "")
        attachment_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 0, attachment_item)
        
        # Importance indicator (column 1)
        importance_icon = "★" if getattr(message, 'is_flagged', False) else ""
        importance_item = QTableWidgetItem(importance_icon)
        importance_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 1, importance_item)
        
        # Threading (empty for single messages)
        threading_item = QTableWidgetItem("")
        threading_item.setData(Qt.ItemDataRole.UserRole, {
            'type': 'single_message', 
            'message': message
        })
        self.setItem(row, 2, threading_item)
        
        # From (display name only)
        from_display_name = self._extract_display_name(message.headers.from_addr)
        from_item = QTableWidgetItem(from_display_name)
        if not message.is_read:
            font = from_item.font()
            font.setBold(True)
            from_item.setFont(font)
        self.setItem(row, 3, from_item)
        
        # Subject
        subject_item = QTableWidgetItem(message.headers.subject or "(No Subject)")
        if not message.is_read:
            font = subject_item.font()
            font.setBold(True)
            subject_item.setFont(font)
        self.setItem(row, 4, subject_item)
        
        # Date (system locale format)
        date_str = self._format_date_system_locale(message.headers.date)
        date_item = QTableWidgetItem(date_str)
        if not message.is_read:
            font = date_item.font()
            font.setBold(True)
            date_item.setFont(font)
        self.setItem(row, 5, date_item)
        
        # Size
        size_str = self._format_size(message.size)
        size_item = QTableWidgetItem(size_str)
        self.setItem(row, 6, size_item)
    
    def clear_messages(self):
        """Clear all messages and threads."""
        self.setRowCount(0)
        self.threads.clear()
    
    def get_selected_message(self) -> Optional[EmailMessage]:
        """Get the currently selected message."""
        current_row = self.currentRow()
        if current_row >= 0:
            item = self.item(current_row, 2)  # Get threading column item (has data, now column 2)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data:
                    if data.get('type') == 'thread_message':
                        return data.get('message')
                    elif data.get('type') == 'single_message':
                        return data.get('message')
                    elif data.get('type') == 'thread_header':
                        # Return latest message from thread
                        thread_id = data.get('thread_id')
                        if thread_id in self.threads:
                            return self.threads[thread_id].get_latest_message()
        return None
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def _on_selection_changed(self):
        """Handle selection change."""
        message = self.get_selected_message()
        if message:
            self.message_selected.emit(message.uid)
    
    def _on_double_clicked(self, item):
        """Handle double click."""
        message = self.get_selected_message()
        if message:
            self.message_double_clicked.emit(message.uid)
    
    def _on_item_clicked(self, item):
        """Handle item click (for expanding/collapsing threads)."""
        if item.column() == 2:  # Threading indicator column (now column 2)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data.get('type') == 'thread_header':
                thread_id = data.get('thread_id')
                self._toggle_thread_expansion(thread_id)
    
    def _toggle_thread_expansion(self, thread_id: str):
        """Toggle expansion of a conversation thread."""
        if thread_id in self.expanded_threads:
            self.expanded_threads.remove(thread_id)
        else:
            self.expanded_threads.add(thread_id)
        
        self._rebuild_display()
    
    def _rebuild_display(self):
        """Rebuild the display with current threading settings."""
        # Store current messages
        all_messages = []
        for thread in self.threads.values():
            all_messages.extend(thread.messages)
        
        if all_messages:
            self.add_messages(all_messages)


class FolderTreeWidget(QTreeWidget):
    """Custom tree widget for displaying email folders."""
    
    folder_selected = pyqtSignal(str, int)  # folder_name, account_id
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.account_items: Dict[int, QTreeWidgetItem] = {}
    
    def setup_ui(self):
        """Setup the folder tree UI."""
        self.setHeaderLabel("Folders")
        self.setRootIsDecorated(True)
        self.setIndentation(20)
        
        # Improve tree appearance
        self.setAlternatingRowColors(True)
        self.setMinimumWidth(200)
        self.setMaximumWidth(350)
        
        # Set better styling with native expand/collapse indicators
        self.setStyleSheet("""
            QTreeWidget {
                outline: none;
                border: 1px solid #d0d0d0;
                background-color: white;
                alternate-background-color: #f5f5f5;
                font-size: 13px;
                show-decoration-selected: 1;
            }
            QTreeWidget::item {
                padding: 4px;
                border: none;
                height: 20px;
            }
            QTreeWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QTreeWidget::item:hover {
                background-color: #e5f3ff;
            }
        """)
        
        # Connect signals
        self.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _is_special_folder(self, folder: FolderInfo) -> bool:
        """Check if folder is a special folder based on IMAP flags."""
        special_flags = {
            '\\Drafts', '\\Sent', '\\Trash', '\\Junk', '\\Archive', 
            '\\Flagged', '\\All', '\\Important'
        }
        return any(flag in special_flags for flag in folder.flags)
    
    def _get_folder_icon_and_type(self, folder: FolderInfo) -> Tuple[str, str]:
        """Get appropriate icon and type for folder based on IMAP flags and name."""
        folder_name = folder.name.upper()
        
        # Check IMAP special-use flags first (RFC 6154)
        if '\\Drafts' in folder.flags:
            return '📝', 'drafts'
        elif '\\Sent' in folder.flags:
            return '📤', 'sent'
        elif '\\Trash' in folder.flags:
            return '🗑️', 'trash'
        elif '\\Junk' in folder.flags:
            return '🚫', 'junk'
        elif '\\Archive' in folder.flags:
            return '📦', 'archive'
        elif '\\Flagged' in folder.flags:
            return '⭐', 'flagged'
        elif '\\All' in folder.flags:
            return '📋', 'all'
        elif '\\Important' in folder.flags:
            return '❗', 'important'
        
        # Fallback to name-based detection for servers without special-use flags
        if folder_name == 'INBOX':
            return '📥', 'inbox'
        elif any(name in folder_name for name in ['SENT', 'SENT ITEMS']):
            return '📤', 'sent'
        elif any(name in folder_name for name in ['DRAFT', 'DRAFTS']):
            return '📝', 'drafts'
        elif any(name in folder_name for name in ['TRASH', 'DELETED', 'DELETED ITEMS']):
            return '🗑️', 'trash'
        elif any(name in folder_name for name in ['SPAM', 'JUNK', 'JUNK EMAIL']):
            return '🚫', 'junk'
        elif any(name in folder_name for name in ['ARCHIVE', 'ARCHIVES']):
            return '📦', 'archive'
        else:
            return '📁', 'regular'
    
    def add_account(self, account: Account, folders: List[FolderInfo]):
        """Add an account and its folders to the tree with proper hierarchy."""
        # Create account item
        account_item = QTreeWidgetItem([account.name])
        account_item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'account', 'account_id': account.id})
        
        # Build folder hierarchy
        self._build_folder_hierarchy(account_item, folders, account.id)
        
        self.addTopLevelItem(account_item)
        self.account_items[account.id] = account_item
        
        # Expand account and INBOX by default
        account_item.setExpanded(True)
        
        # Find and expand INBOX and any folder with children
        for i in range(account_item.childCount()):
            child = account_item.child(i)
            # Check the stored folder name, not the display text (which has icons)
            data = child.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get('folder_name') == 'INBOX':
                child.setExpanded(True)
                # Also expand any subfolders under INBOX
                self._expand_folder_with_children(child)
                break
        
        # Force tree widget to update its display
        self.update()
        self.repaint()
    
    def _expand_folder_with_children(self, folder_item: QTreeWidgetItem):
        """Recursively expand folders that have children."""
        if folder_item.childCount() > 0:
            folder_item.setExpanded(True)
            for i in range(folder_item.childCount()):
                child = folder_item.child(i)
                self._expand_folder_with_children(child)
    
    def _build_folder_hierarchy(self, account_item: QTreeWidgetItem, folders: List[FolderInfo], account_id: int):
        """Build hierarchical folder structure from flat folder list."""
        if not folders:
            return
            
        # Dictionary to store created folder items by path
        folder_items = {}
        
        # Separate folders by type for proper ordering
        inbox_folder = None
        special_folders = []
        regular_folders = []
        
        for folder in folders:
            if folder.name.upper() == 'INBOX':
                inbox_folder = folder
            elif self._is_special_folder(folder):
                special_folders.append(folder)
            else:
                regular_folders.append(folder)
        
        # First, create INBOX at the top
        if inbox_folder:
            self._create_folder_item(inbox_folder, account_item, account_id, folder_items)
        
        # Then create special folders at root level (promoted from subfolders)
        for folder in special_folders:
            self._create_folder_item(folder, account_item, account_id, folder_items)
        
        # Then create other regular root level folders (no delimiter in name)
        root_folders = [f for f in regular_folders if not f.delimiter or f.delimiter not in f.name]
        for folder in root_folders:
            self._create_folder_item(folder, account_item, account_id, folder_items)
        
        # Finally create nested folders level by level (excluding special folders)
        remaining_folders = [f for f in regular_folders if f.delimiter and f.delimiter in f.name]
        remaining_folders.sort(key=lambda f: f.name.count(f.delimiter or '.'))
        
        for folder in remaining_folders:
            delimiter = folder.delimiter or '.'
            path_parts = folder.name.split(delimiter)
            
            # Find the parent item
            parent_path = delimiter.join(path_parts[:-1])
            parent_item = folder_items.get(parent_path, account_item)
            
            # If parent doesn't exist, create parent hierarchy first
            if parent_path not in folder_items and parent_path:
                parent_item = self._ensure_parent_hierarchy(parent_path, delimiter, account_item, account_id, folder_items, folders)
            
            # Create the folder item
            self._create_folder_item(folder, parent_item, account_id, folder_items)
        
                 # Expand the account item and INBOX by default to show hierarchy
        account_item.setExpanded(True)
        if 'INBOX' in folder_items:
            folder_items['INBOX'].setExpanded(True)
            
        # Also expand any folders that have children to show the full structure
        for folder_name, item in folder_items.items():
            if item.childCount() > 0:
                item.setExpanded(True)
    
    def _create_folder_item(self, folder: FolderInfo, parent_item: QTreeWidgetItem, account_id: int, folder_items: dict):
        """Create a tree widget item for a folder."""
        # Determine display name
        if self._is_special_folder(folder):
            # For special folders, use friendly names instead of technical names
            display_name = self._get_special_folder_display_name(folder)
        else:
            # For regular folders, use the last part of the path
            delimiter = folder.delimiter or '.'
            if delimiter in folder.name:
                display_name = folder.name.split(delimiter)[-1]
            else:
                display_name = folder.name
        
        # Create folder item
        folder_item = QTreeWidgetItem([display_name])
        folder_item.setData(0, Qt.ItemDataRole.UserRole, {
            'type': 'folder',
            'folder_name': folder.name,
            'account_id': account_id,
            'folder_info': folder
        })
        
        # Add unread count if available
        if folder.unseen > 0:
            folder_item.setText(0, f"{display_name} ({folder.unseen})")
        
        # Add visual icons based on folder type
        current_text = folder_item.text(0)
        icon, folder_type = self._get_folder_icon_and_type(folder)
        folder_item.setText(0, f"{icon} {current_text}")
        
        # Add to parent and store in lookup
        parent_item.addChild(folder_item)
        folder_items[folder.name] = folder_item
        
        return folder_item
    
    def _get_special_folder_display_name(self, folder: FolderInfo) -> str:
        """Get user-friendly display name for special folders."""
        # Check IMAP special-use flags first (RFC 6154)
        if '\\Drafts' in folder.flags:
            return 'Drafts'
        elif '\\Sent' in folder.flags:
            return 'Sent'
        elif '\\Trash' in folder.flags:
            return 'Trash'
        elif '\\Junk' in folder.flags:
            return 'Spam'
        elif '\\Archive' in folder.flags:
            return 'Archive'
        elif '\\Flagged' in folder.flags:
            return 'Starred'
        elif '\\All' in folder.flags:
            return 'All Mail'
        elif '\\Important' in folder.flags:
            return 'Important'
        else:
            # Fallback to last part of folder name
            delimiter = folder.delimiter or '.'
            if delimiter in folder.name:
                return folder.name.split(delimiter)[-1]
            else:
                return folder.name
    
    def _ensure_parent_hierarchy(self, parent_path: str, delimiter: str, account_item: QTreeWidgetItem, 
                                account_id: int, folder_items: dict, all_folders: List[FolderInfo]) -> QTreeWidgetItem:
        """Ensure parent folder hierarchy exists."""
        path_parts = parent_path.split(delimiter)
        current_path = ""
        current_parent = account_item
        
        for part in path_parts:
            if current_path:
                current_path += delimiter + part
            else:
                current_path = part
            
            if current_path not in folder_items:
                # Check if this is a real folder
                real_folder = next((f for f in all_folders if f.name == current_path), None)
                
                if real_folder:
                    # Create real folder item
                    folder_item = self._create_folder_item(real_folder, current_parent, account_id, folder_items)
                else:
                    # Create placeholder folder item
                    folder_item = QTreeWidgetItem([part])
                    folder_item.setData(0, Qt.ItemDataRole.UserRole, {
                        'type': 'folder',
                        'folder_name': current_path,
                        'account_id': account_id,
                        'folder_info': None
                    })
                    folder_item.setText(0, f"📁 {part}")
                    current_parent.addChild(folder_item)
                    folder_items[current_path] = folder_item
                
                current_parent = folder_items[current_path]
            else:
                current_parent = folder_items[current_path]
        
        return current_parent
    
    def _get_or_create_folder_item(self, folder_items: dict, folder_path: str, 
                                  account_item: QTreeWidgetItem, account_id: int, 
                                  delimiter: str, all_folders: List[FolderInfo]) -> QTreeWidgetItem:
        """Get existing folder item or create hierarchy for the given path."""
        if folder_path in folder_items:
            return folder_items[folder_path]
        
        # Split path and build hierarchy
        path_parts = folder_path.split(delimiter)
        current_path = ""
        current_parent = account_item
        
        for i, part in enumerate(path_parts):
            if current_path:
                current_path += delimiter + part
            else:
                current_path = part
            
            if current_path not in folder_items:
                # Create folder item for this level
                folder_item = QTreeWidgetItem([part])
                
                # Try to find folder info for this path
                folder_info = next((f for f in all_folders if f.name == current_path), None)
                
                folder_item.setData(0, Qt.ItemDataRole.UserRole, {
                    'type': 'folder',
                    'folder_name': current_path,
                    'account_id': account_id,
                    'folder_info': folder_info
                })
                
                # Add unread count if folder info available
                if folder_info and folder_info.unseen > 0:
                    folder_item.setText(0, f"{part} ({folder_info.unseen})")
                
                # Add icon based on folder type
                current_text = folder_item.text(0)
                if folder_info:
                    icon, folder_type = self._get_folder_icon_and_type(folder_info)
                    folder_item.setText(0, f"{icon} {current_text}")
                else:
                    # Fallback for folders without info - use simple heuristics
                    if part.upper() == "INBOX":
                        folder_item.setText(0, f"📥 {current_text}")
                    else:
                        folder_item.setText(0, f"📁 {current_text}")
                
                current_parent.addChild(folder_item)
                folder_items[current_path] = folder_item
                current_parent = folder_item
            else:
                current_parent = folder_items[current_path]
        
        return current_parent
    
    def _on_selection_changed(self):
        """Handle selection change."""
        current_item = self.currentItem()
        if current_item:
            data = current_item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get('type') == 'folder':
                self.folder_selected.emit(data['folder_name'], data['account_id'])


class MessagePreviewWidget(QTextEdit):
    """Custom text edit for displaying email message content with attachment support."""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.current_message = None
    
    def setup_ui(self):
        """Setup the message preview UI."""
        self.setReadOnly(True)
        self.setMinimumHeight(300)
        
        # Enable hyperlinks (alternative method for compatibility)
        try:
            self.setOpenExternalLinks(True)
        except AttributeError:
            # Fallback for versions where this method is not available
            pass
    
    def show_message(self, message: EmailMessage):
        """Display an email message with attachment support."""
        self.current_message = message
        html_content = self._build_message_html(message)
        self.setHtml(html_content)
    
    def clear_message(self):
        """Clear the message display."""
        self.current_message = None
        self.clear()
    
    def _build_message_html(self, message: EmailMessage) -> str:
        """Build HTML representation of the message with attachments."""
        html_parts = []
        
        # Message headers
        html_parts.append("""
        <div style="background-color: #f5f5f5; padding: 10px; margin-bottom: 10px; border: 1px solid #ddd;">
        """)
        
        html_parts.append(f"<p><strong>From:</strong> {html.escape(message.headers.from_addr)}</p>")
        
        if hasattr(message.headers, 'to_addrs') and message.headers.to_addrs:
            to_str = ', '.join(message.headers.to_addrs)
            html_parts.append(f"<p><strong>To:</strong> {html.escape(to_str)}</p>")
        elif hasattr(message.headers, 'to') and message.headers.to:
            html_parts.append(f"<p><strong>To:</strong> {html.escape(message.headers.to)}</p>")
        
        if hasattr(message.headers, 'cc_addrs') and message.headers.cc_addrs:
            cc_str = ', '.join(message.headers.cc_addrs)
            html_parts.append(f"<p><strong>CC:</strong> {html.escape(cc_str)}</p>")
        elif hasattr(message.headers, 'cc') and message.headers.cc:
            html_parts.append(f"<p><strong>CC:</strong> {html.escape(message.headers.cc)}</p>")
        
        html_parts.append(f"<p><strong>Subject:</strong> {html.escape(message.headers.subject or '(No Subject)')}</p>")
        html_parts.append(f"<p><strong>Date:</strong> {message.headers.date.strftime('%A, %B %d, %Y at %I:%M %p')}</p>")
        
        # Attachments section
        if message.attachments:
            html_parts.append(self._build_attachments_html(message.attachments))
        
        html_parts.append("</div>")
        
        # Message body
        html_parts.append('<div style="margin-top: 15px;">')
        if message.html_content:
            # Clean HTML content for security
            cleaned_html = self._clean_html_content(message.html_content)
            html_parts.append(cleaned_html)
        elif message.text_content:
            # Convert plain text to HTML
            text_lines = message.text_content.split('\n')
            for line in text_lines:
                html_parts.append(f"<p>{html.escape(line)}</p>")
        else:
            html_parts.append("<p><em>No content to display</em></p>")
        
        html_parts.append('</div>')
        
        return ''.join(html_parts)
    
    def _build_attachments_html(self, attachments) -> str:
        """Build HTML for attachment list with preview and download options."""
        html_parts = []
        
        html_parts.append('<div style="margin-top: 10px; padding: 8px; background-color: #fff9c4; border: 1px solid #f0e68c;">')
        html_parts.append('<p><strong>📎 Attachments:</strong></p>')
        html_parts.append('<ul style="margin-left: 20px;">')
        
        for i, attachment in enumerate(attachments):
            file_size = self._format_attachment_size(attachment.get('size', 0))
            filename = attachment.get('filename', f'attachment_{i}')
            content_type = attachment.get('content_type', 'application/octet-stream')
            
            # Determine if we can preview this attachment type
            is_previewable = self._is_previewable_type(content_type)
            preview_icon = "👁️" if is_previewable else "📄"
            
            html_parts.append(f'''
            <li style="margin-bottom: 5px;">
                {preview_icon} <strong>{html.escape(filename)}</strong> 
                <span style="color: #666;">({file_size})</span>
                <span style="color: #888; font-size: 0.9em;">[{content_type}]</span>
                <br>
                <small>
                    <a href="#" onclick="downloadAttachment({i})" style="color: #0066cc;">💾 Download</a>
                    {' | <a href="#" onclick="previewAttachment(' + str(i) + ')" style="color: #0066cc;">👁️ Preview</a>' if is_previewable else ''}
                </small>
            </li>
            ''')
        
        html_parts.append('</ul>')
        html_parts.append('<p style="font-size: 0.9em; color: #666; margin-top: 8px;">')
        html_parts.append('<em>Click Download to save attachments to your computer</em>')
        html_parts.append('</p>')
        html_parts.append('</div>')
        
        return ''.join(html_parts)
    
    def _format_attachment_size(self, size_bytes: int) -> str:
        """Format attachment size in human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def _is_previewable_type(self, content_type: str) -> bool:
        """Check if attachment type can be previewed."""
        previewable_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
            'text/plain', 'text/html', 'application/pdf'
        ]
        return content_type.lower() in previewable_types
    
    def _clean_html_content(self, html_content: str) -> str:
        """Clean HTML content for security (basic implementation)."""
        # Basic HTML cleaning - in production, use a proper HTML sanitizer
        # Remove script tags and dangerous attributes
        import re
        
        # Remove script tags
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove dangerous attributes
        dangerous_attrs = ['onload', 'onclick', 'onmouseover', 'onerror', 'onchange']
        for attr in dangerous_attrs:
            html_content = re.sub(f'{attr}="[^"]*"', '', html_content, flags=re.IGNORECASE)
            html_content = re.sub(f"{attr}='[^']*'", '', html_content, flags=re.IGNORECASE)
        
        return html_content
    
    def download_attachment(self, attachment_index: int):
        """Download attachment to user's computer."""
        if not self.current_message or not self.current_message.attachments:
            return
        
        if attachment_index >= len(self.current_message.attachments):
            return
        
        try:
            from PyQt6.QtWidgets import QFileDialog
            import os
            
            attachment = self.current_message.attachments[attachment_index]
            filename = attachment.get('filename', f'attachment_{attachment_index}')
            
            # Ask user where to save the file
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Attachment",
                filename,
                "All Files (*.*)"
            )
            
            if save_path:
                # Get attachment content from email manager
                content = self._get_attachment_content(attachment_index)
                if content:
                    with open(save_path, 'wb') as f:
                        f.write(content)
                    
                    QMessageBox.information(
                        self,
                        "Download Complete",
                        f"Attachment saved to:\n{save_path}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Download Failed",
                        "Failed to retrieve attachment content"
                    )
                    
        except Exception as e:
            QMessageBox.critical(
                self,
                "Download Error",
                f"Failed to download attachment: {e}"
            )
    
    def _get_attachment_content(self, attachment_index: int) -> Optional[bytes]:
        """Get attachment content from the email (placeholder implementation)."""
        # This would need to be implemented in the email manager
        # to retrieve the actual attachment content from the IMAP server
        try:
            if self.current_message and hasattr(self.current_message, 'get_attachment_content'):
                return self.current_message.get_attachment_content(attachment_index)
        except Exception:
            pass
        return None


class EmailSearchWidget(QFrame):
    """Advanced email search widget with multiple criteria."""
    
    search_requested = pyqtSignal(dict)  # search_criteria
    search_cleared = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setMaximumHeight(120)
        self.hide()  # Initially hidden
    
    def setup_ui(self):
        """Setup the search UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Title
        title_label = QLabel("Search Email")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title_label)
        
        # Search criteria
        criteria_layout = QHBoxLayout()
        
        # Search text
        criteria_layout.addWidget(QLabel("Text:"))
        self.search_text = QLineEdit()
        self.search_text.setPlaceholderText("Search in subject, from, body...")
        self.search_text.returnPressed.connect(self.perform_search)
        criteria_layout.addWidget(self.search_text)
        
        # Search scope
        criteria_layout.addWidget(QLabel("In:"))
        self.search_scope = QComboBox()
        self.search_scope.addItems(["All", "Subject", "From", "Body", "To/CC"])
        criteria_layout.addWidget(self.search_scope)
        
        # Date range
        criteria_layout.addWidget(QLabel("Date:"))
        self.date_range = QComboBox()
        self.date_range.addItems([
            "Any time", "Today", "Yesterday", "This week", 
            "Last week", "This month", "Last month", "Custom range"
        ])
        criteria_layout.addWidget(self.date_range)
        
        layout.addLayout(criteria_layout)
        
        # Additional filters
        filters_layout = QHBoxLayout()
        
        self.has_attachments = QCheckBox("Has attachments")
        filters_layout.addWidget(self.has_attachments)
        
        self.unread_only = QCheckBox("Unread only")
        filters_layout.addWidget(self.unread_only)
        
        self.flagged_only = QCheckBox("Flagged only")
        filters_layout.addWidget(self.flagged_only)
        
        filters_layout.addStretch()
        
        # Search buttons
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.perform_search)
        search_btn.setDefault(True)
        filters_layout.addWidget(search_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_search)
        filters_layout.addWidget(clear_btn)
        
        close_btn = QPushButton("×")
        close_btn.setMaximumWidth(30)
        close_btn.clicked.connect(self.hide)
        filters_layout.addWidget(close_btn)
        
        layout.addLayout(filters_layout)
    
    def perform_search(self):
        """Emit search request with current criteria."""
        criteria = {
            'text': self.search_text.text().strip(),
            'scope': self.search_scope.currentText(),
            'date_range': self.date_range.currentText(),
            'has_attachments': self.has_attachments.isChecked(),
            'unread_only': self.unread_only.isChecked(),
            'flagged_only': self.flagged_only.isChecked()
        }
        self.search_requested.emit(criteria)
    
    def clear_search(self):
        """Clear all search criteria."""
        self.search_text.clear()
        self.search_scope.setCurrentIndex(0)
        self.date_range.setCurrentIndex(0)
        self.has_attachments.setChecked(False)
        self.unread_only.setChecked(False)
        self.flagged_only.setChecked(False)
        self.search_cleared.emit()
    
    def focus_search(self):
        """Focus the search text field."""
        self.search_text.setFocus()
        self.search_text.selectAll()


class EmailView(QWidget):
    """
    Main email view with folder tree, message list, and preview.
    
    Provides Outlook-style three-pane interface with comprehensive
    email functionality including search, composition, and management.
    """
    
    # Signal to communicate status messages to main window
    status_message = pyqtSignal(str, int)  # message, timeout
    
    def __init__(self, email_manager: EmailManager, account_manager=None):
        super().__init__()
        self.email_manager = email_manager
        self.account_manager = account_manager
        self.current_folder = None
        self.current_account_id = None
        self.accounts = []
        
        self.setup_ui()
        self.setup_connections()
        
        # Initialize preview position to default
        self.preview_position = "bottom"
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_current_folder)
        self.refresh_timer.start(300000)  # 5 minutes
    
    def setup_ui(self):
        """Setup the main UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        self.toolbar = QToolBar()
        self.setup_toolbar()
        layout.addWidget(self.toolbar)
        
        # Create search widget
        self.search_widget = EmailSearchWidget()
        self.search_widget.search_requested.connect(self.perform_search)
        self.search_widget.search_cleared.connect(self.clear_search)
        layout.addWidget(self.search_widget)
        
        # Create main splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left pane: Folder tree
        self.folder_tree = FolderTreeWidget()
        self.main_splitter.addWidget(self.folder_tree)
        
        # Right pane: Message list and preview
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Message list
        self.message_list = ThreadedMessageListWidget()
        self.right_splitter.addWidget(self.message_list)
        
        # Message preview
        self.message_preview = MessagePreviewWidget()
        self.right_splitter.addWidget(self.message_preview)
        
        # Set splitter proportions - make message list much bigger
        self.right_splitter.setSizes([500, 300])  # Give more space to message list
        
        self.main_splitter.addWidget(self.right_splitter)
        self.main_splitter.setSizes([300, 800])  # Give more space to right pane
        
        layout.addWidget(self.main_splitter)
        
        # Remove own status bar - will use main window's status bar
    
    def setup_toolbar(self):
        """Setup the email toolbar."""
        # New email button
        new_email_action = QAction("New Email", self)
        new_email_action.triggered.connect(self.compose_new_email)
        self.toolbar.addAction(new_email_action)
        
        self.toolbar.addSeparator()
        
        # Reply buttons
        reply_action = QAction("Reply", self)
        reply_action.triggered.connect(self.reply_to_message)
        self.toolbar.addAction(reply_action)
        
        reply_all_action = QAction("Reply All", self)
        reply_all_action.triggered.connect(self.reply_all_to_message)
        self.toolbar.addAction(reply_all_action)
        
        forward_action = QAction("Forward", self)
        forward_action.triggered.connect(self.forward_message)
        self.toolbar.addAction(forward_action)
        
        self.toolbar.addSeparator()
        
        # Delete button
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.delete_message)
        self.toolbar.addAction(delete_action)
        
        self.toolbar.addSeparator()
        
        # Search button
        search_action = QAction("Search", self)
        search_action.setShortcut(QKeySequence("Ctrl+F"))
        search_action.triggered.connect(self.toggle_search)
        self.toolbar.addAction(search_action)
        
        # Quick search field
        self.quick_search = QLineEdit()
        self.quick_search.setPlaceholderText("Quick search...")
        self.quick_search.setMaximumWidth(200)
        self.quick_search.returnPressed.connect(self.perform_quick_search)
        self.toolbar.addWidget(self.quick_search)
        
        self.toolbar.addSeparator()
        
        # Refresh button
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_current_folder)
        self.toolbar.addAction(refresh_action)
        
        # Threading toggle button
        threading_action = QAction("Threading", self)
        threading_action.setCheckable(True)
        threading_action.setChecked(True)
        threading_action.triggered.connect(self._toggle_threading)
        self.toolbar.addAction(threading_action)
        
        self.toolbar.addSeparator()
    
    def setup_connections(self):
        """Setup signal connections."""
        self.folder_tree.folder_selected.connect(self.on_folder_selected)
        self.message_list.message_selected.connect(self.on_message_selected)
        self.message_list.message_double_clicked.connect(self.on_message_double_clicked)
    
    def set_config(self, config):
        """Set the app config for column width persistence."""
        self.config = config
        self.message_list.set_config(config)
        # Load preview pane position from config
        self._load_preview_pane_position()
    
    def _load_preview_pane_position(self):
        """Load preview pane position from config."""
        if not self.config:
            return
        
        position = self.config.ui.preview_pane_position
        # Apply the position without saving it back to config (to avoid infinite loop)
        self._apply_preview_pane_position(position)
    
    def _apply_preview_pane_position(self, position: str):
        """
        Apply the preview pane position without saving to config.
        
        Args:
            position: Position of preview pane: 'off', 'right', or 'bottom'
        """
        if not hasattr(self, 'main_splitter') or not hasattr(self, 'right_splitter'):
            return
        
        # Store the position
        self.preview_position = position
        
        if position == "off":
            # Hide the preview pane
            self.message_preview.setVisible(False)
        elif position == "right":
            # Horizontal layout: message list on left, preview on right
            self.message_preview.setVisible(True)
            
            # Change right splitter to horizontal
            self.right_splitter.setOrientation(Qt.Orientation.Horizontal)
            # Adjust proportions: more space for message list
            self.right_splitter.setSizes([400, 300])
        elif position == "bottom":
            # Vertical layout: message list on top, preview on bottom
            self.message_preview.setVisible(True)
            
            # Change right splitter to vertical
            self.right_splitter.setOrientation(Qt.Orientation.Vertical)
            # Adjust proportions: more space for message list
            self.right_splitter.setSizes([500, 300])
    
    def set_preview_pane_position(self, position: str):
        """
        Set the preview pane position and save to config.
        
        Args:
            position: Position of preview pane: 'off', 'right', or 'bottom'
        """
        # Apply the position
        self._apply_preview_pane_position(position)
        
        # Update config if available
        if hasattr(self, 'config') and self.config:
            self.config.ui.preview_pane_position = position
            self.config.save()
    
    def load_accounts(self, accounts: List[Account]):
        """Load accounts and their folders into the folder tree."""
        self.accounts = accounts  # Store accounts for composer functions
        
        # Clear existing accounts to prevent duplicates
        self.folder_tree.clear()
        
        for account in accounts:
            try:
                # Try to get real folders from email manager
                folders = self.email_manager.get_folders(account.id)
                if not folders:
                    # Fallback to sample folders if no real folders available yet
                    folders = self._create_sample_folders()
            except Exception as e:
                # Use sample folders if there's an error getting real folders
                folders = self._create_sample_folders()
            
            # Add account and folders to tree
            self.folder_tree.add_account(account, folders)
            
            # Auto-select INBOX for first account (but don't load messages yet)
            if not hasattr(self, '_inbox_selected') and folders:
                inbox_folder = next((f for f in folders if f.name.upper() == 'INBOX'), folders[0])
                self.current_account_id = account.id
                self.current_folder = inbox_folder.name
                self._inbox_selected = True
                
                # Show connecting status
                self.status_message.emit("Connecting to email server...", 0)
                
        # Note: Actual folder and message loading will happen asynchronously
        # when email connections are established in the background
    

    
    def _create_sample_folders(self):
        """Create sample folder structure for demonstration."""
        from ...core.email.imap_client import FolderInfo
        
        return [
            FolderInfo(name="INBOX", delimiter="/", flags=["\\HasNoChildren"], exists=27, unseen=5),
            FolderInfo(name="Sent", delimiter="/", flags=["\\HasNoChildren"], exists=15, unseen=0),
            FolderInfo(name="Drafts", delimiter="/", flags=["\\HasNoChildren"], exists=3, unseen=0),
            FolderInfo(name="Trash", delimiter="/", flags=["\\HasNoChildren"], exists=8, unseen=0),
            FolderInfo(name="Spam", delimiter="/", flags=["\\HasNoChildren"], exists=12, unseen=2),
            FolderInfo(name="Archive", delimiter="/", flags=["\\HasNoChildren"], exists=156, unseen=0),
        ]
    
    @pyqtSlot(str, int)
    def on_folder_selected(self, folder_name: str, account_id: int):
        """Handle folder selection."""
        self.current_folder = folder_name
        self.current_account_id = account_id
        self.load_messages()
    
    @pyqtSlot(int)
    def on_message_selected(self, uid: int):
        """Handle message selection."""
        try:
            # Mark as read
            self.email_manager.mark_as_read(uid, self.current_folder, self.current_account_id)
            
            # Get full message with body
            message = self.email_manager.get_message(
                uid, self.current_folder, include_body=True, account_id=self.current_account_id
            )
            
            if message:
                self.message_preview.show_message(message)
            else:
                self.message_preview.clear_message()
                
        except Exception as e:
            self.status_message.emit(f"Failed to load message: {e}", 5000)
    
    @pyqtSlot(int)
    def on_message_double_clicked(self, uid: int):
        """Handle message double click."""
        self.status_message.emit("Opening message in new window (not implemented yet)", 3000)
    
    def load_messages(self):
        """Load messages for the current folder."""
        if not self.current_account_id:
            return

        try:
            self.status_message.emit("Loading messages...", 0)
            
            # Clear current messages
            self.message_list.clear_messages()
            self.message_preview.clear_message()
            
            # Get recent messages from the actual email server
            messages = self.email_manager.get_recent_messages(
                self.current_folder, limit=100, account_id=self.current_account_id
            )
            
            if messages:
                # Add real messages to list
                self.message_list.add_messages(messages)
                self.status_message.emit(f"Loaded {len(messages)} messages", 3000)
            else:
                # No messages found or connection not ready
                self.status_message.emit("No messages found or connection not established", 3000)
            
        except Exception as e:
            # Clear messages on error
            self.message_list.clear_messages()
            self.status_message.emit(f"Failed to load messages: {e}", 5000)
    

    
    def refresh_current_folder(self):
        """Refresh the current folder."""
        if self.current_folder and self.current_account_id:
            self.load_messages()
    
    def refresh_folders_and_messages(self):
        """Refresh folders and messages after connections are established."""
        if not self.accounts:
            return
            
        # Update folder tree with real folders from server
        for account in self.accounts:
            try:
                # Get actual folders from server
                folders = self.email_manager.get_folders(account.id)
                
                if folders:
                    # Update the folder tree with real folder data
                    # For now, we'll just clear and re-add (could be optimized)
                    self.folder_tree.clear()
                    for acc in self.accounts:
                        real_folders = self.email_manager.get_folders(acc.id)
                        if real_folders:
                            self.folder_tree.add_account(acc, real_folders)
                        else:
                            # Keep sample folders if connection failed
                            self.folder_tree.add_account(acc, self._create_sample_folders())
                    
                    # Load messages for current folder
                    if self.current_folder and self.current_account_id:
                        self.load_messages()
                    break  # Only update once when first account succeeds
                    
            except Exception as e:
                self.status_message.emit(f"Failed to refresh folders for {account.name}: {e}", 5000)
    
    def compose_new_email(self):
        """Open new email composition window."""
        if not self.accounts:
            QMessageBox.information(
                self, 
                "No Accounts", 
                "Please set up an email account first."
            )
            return
        
        try:
            composer = EmailComposer(self.email_manager, self.accounts, parent=self)
            composer.email_sent.connect(self._on_email_sent)
            composer.exec()
        except Exception as e:
            self.status_message.emit(f"Failed to open composer: {e}", 5000)
    
    def reply_to_message(self):
        """Reply to selected message."""
        message = self.message_list.get_selected_message()
        if not message:
            self.status_message.emit("Please select a message to reply to", 3000)
            return
        
        if not self.accounts:
            QMessageBox.information(
                self, 
                "No Accounts", 
                "Please set up an email account first."
            )
            return
        
        try:
            # Get full message with body content for reply
            full_message = self.email_manager.get_message(
                message.uid, self.current_folder, include_body=True, 
                account_id=self.current_account_id
            )
            
            if full_message:
                composer = EmailComposer(
                    self.email_manager, 
                    self.accounts, 
                    reply_to_message=full_message,
                    parent=self
                )
                composer.email_sent.connect(self._on_email_sent)
                composer.exec()
            else:
                self.status_message.emit("Failed to load message content for reply", 5000)
                
        except Exception as e:
            self.status_message.emit(f"Failed to open reply: {e}", 5000)
    
    def reply_all_to_message(self):
        """Reply all to selected message."""
        message = self.message_list.get_selected_message()
        if not message:
            self.status_message.emit("Please select a message to reply to", 3000)
            return
        
        if not self.accounts:
            QMessageBox.information(
                self, 
                "No Accounts", 
                "Please set up an email account first."
            )
            return
        
        try:
            # Get full message with body content for reply
            full_message = self.email_manager.get_message(
                message.uid, self.current_folder, include_body=True, 
                account_id=self.current_account_id
            )
            
            if full_message:
                # For reply all, we'll create the composer and then modify the recipients
                composer = EmailComposer(
                    self.email_manager, 
                    self.accounts, 
                    reply_to_message=full_message,
                    parent=self
                )
                
                # Add CC recipients for reply all
                self._setup_reply_all_recipients(composer, full_message)
                
                composer.email_sent.connect(self._on_email_sent)
                composer.exec()
            else:
                self.status_message.emit("Failed to load message content for reply", 5000)
                
        except Exception as e:
            self.status_message.emit(f"Failed to open reply all: {e}", 5000)
    
    def forward_message(self):
        """Forward selected message."""
        message = self.message_list.get_selected_message()
        if not message:
            self.status_message.emit("Please select a message to forward", 3000)
            return
        
        if not self.accounts:
            QMessageBox.information(
                self, 
                "No Accounts", 
                "Please set up an email account first."
            )
            return
        
        try:
            # Get full message with body content for forwarding
            full_message = self.email_manager.get_message(
                message.uid, self.current_folder, include_body=True, 
                account_id=self.current_account_id
            )
            
            if full_message:
                composer = EmailComposer(self.email_manager, self.accounts, parent=self)
                self._setup_forward_content(composer, full_message)
                composer.email_sent.connect(self._on_email_sent)
                composer.exec()
            else:
                self.status_message.emit("Failed to load message content for forwarding", 5000)
                
        except Exception as e:
            self.status_message.emit(f"Failed to open forward: {e}", 5000)
    
    def _setup_reply_all_recipients(self, composer: EmailComposer, message: EmailMessage):
        """Setup recipients for reply all."""
        try:
            # Parse original recipients
            original_to = []
            original_cc = []
            
            # Add original To recipients to CC (excluding our own account)
            if hasattr(message.headers, 'to_addrs') and message.headers.to_addrs:
                for addr in message.headers.to_addrs:
                    addr = addr.strip()
                    if addr and not self._is_own_address(addr):
                        original_to.append(addr)
            elif hasattr(message.headers, 'to') and message.headers.to:
                for addr in message.headers.to.split(','):
                    addr = addr.strip()
                    if addr and not self._is_own_address(addr):
                        original_to.append(addr)
            
            # Add original CC recipients
            if hasattr(message.headers, 'cc_addrs') and message.headers.cc_addrs:
                for addr in message.headers.cc_addrs:
                    addr = addr.strip()
                    if addr and not self._is_own_address(addr):
                        original_cc.append(addr)
            elif hasattr(message.headers, 'cc') and message.headers.cc:
                for addr in message.headers.cc.split(','):
                    addr = addr.strip()
                    if addr and not self._is_own_address(addr):
                        original_cc.append(addr)
            
            # Set CC field in composer (To field is already set to sender)
            all_cc = original_to + original_cc
            if all_cc:
                composer.cc_edit.setText(', '.join(all_cc))
                
        except Exception as e:
            self.status_message.emit(f"Warning: Could not setup reply all recipients: {e}", 5000)
    
    def _setup_forward_content(self, composer: EmailComposer, message: EmailMessage):
        """Setup content for forwarding a message."""
        try:
            # Set subject with "Fwd: " prefix
            original_subject = message.headers.subject or ""
            if not original_subject.startswith("Fwd: "):
                forward_subject = f"Fwd: {original_subject}"
            else:
                forward_subject = original_subject
            composer.subject_edit.setText(forward_subject)
            
            # Create forward content
            date_str = message.headers.date.strftime("%A, %B %d, %Y at %I:%M %p")
            
            forward_html = f"""
            <br><br>
            <div style="border-left: 2px solid #0078d4; padding-left: 10px; margin: 10px 0;">
                <p><strong>---------- Forwarded message ----------</strong><br>
                <strong>From:</strong> {html.escape(message.headers.from_addr)}<br>
                <strong>Date:</strong> {date_str}<br>
                <strong>Subject:</strong> {html.escape(message.headers.subject or "")}<br>
                <strong>To:</strong> {html.escape(getattr(message.headers, 'to', ''))}</p>
                
                <div style="margin-top: 10px;">
                    {message.html_content or html.escape(message.text_content or "")}
                </div>
            </div>
            """
            
            composer.editor.setHtml(forward_html)
            
            # Position cursor at the beginning for user to add their message
            cursor = composer.editor.textCursor()
            cursor.setPosition(0)
            composer.editor.setTextCursor(cursor)
            
        except Exception as e:
            self.status_message.emit(f"Warning: Could not setup forward content: {e}", 5000)
    
    def _is_own_address(self, email_address: str) -> bool:
        """Check if an email address belongs to one of our accounts."""
        for account in self.accounts:
            if account.email_address.lower() == email_address.lower():
                return True
        return False
    
    @pyqtSlot(bool)
    def _on_email_sent(self, success: bool):
        """Handle email sent notification."""
        if success:
            self.status_message.emit("Email sent successfully!", 3000)
            # Refresh the current folder to show the sent message in Sent folder
            # if we're currently viewing the Sent folder
            if self.current_folder and 'sent' in self.current_folder.lower():
                QTimer.singleShot(1000, self.refresh_current_folder)
        else:
            self.status_message.emit("Failed to send email", 3000)
    
    def delete_message(self):
        """Delete selected message."""
        message = self.message_list.get_selected_message()
        if message:
            try:
                self.email_manager.delete_message(
                    message.uid, self.current_folder, permanent=False, 
                    account_id=self.current_account_id
                )
                self.refresh_current_folder()
                self.status_message.emit("Message deleted", 3000)
            except Exception as e:
                self.status_message.emit(f"Failed to delete message: {e}", 5000)
    
    def toggle_search(self):
        """Toggle the advanced search widget."""
        if self.search_widget.isVisible():
            self.search_widget.hide()
        else:
            self.search_widget.show()
            self.search_widget.focus_search()
    
    def perform_quick_search(self):
        """Perform quick search from toolbar."""
        text = self.quick_search.text().strip()
        if text:
            criteria = {
                'text': text,
                'scope': 'All',
                'date_range': 'Any time',
                'has_attachments': False,
                'unread_only': False,
                'flagged_only': False
            }
            self.perform_search(criteria)
    
    @pyqtSlot(dict)
    def perform_search(self, criteria: dict):
        """Perform email search with given criteria."""
        if not self.current_account_id:
            return
        
        try:
            self.status_message.emit("Searching...", 0)
            
            # Clear current messages
            self.message_list.clear_messages()
            self.message_preview.clear_message()
            
            # Build search criteria for IMAP
            search_terms = []
            
            # Text search
            if criteria['text']:
                text = criteria['text']
                scope = criteria['scope']
                
                if scope == 'All':
                    search_terms.append(f'(OR SUBJECT "{text}" FROM "{text}" BODY "{text}")')
                elif scope == 'Subject':
                    search_terms.append(f'SUBJECT "{text}"')
                elif scope == 'From':
                    search_terms.append(f'FROM "{text}"')
                elif scope == 'Body':
                    search_terms.append(f'BODY "{text}"')
                elif scope == 'To/CC':
                    search_terms.append(f'(OR TO "{text}" CC "{text}")')
            
            # Date range
            if criteria['date_range'] != 'Any time':
                date_term = self._build_date_search_term(criteria['date_range'])
                if date_term:
                    search_terms.append(date_term)
            
            # Additional filters
            if criteria['has_attachments']:
                search_terms.append('HAS_ATTACHMENT')
            
            if criteria['unread_only']:
                search_terms.append('UNSEEN')
            
            if criteria['flagged_only']:
                search_terms.append('FLAGGED')
            
            # Combine search terms
            search_query = ' '.join(search_terms) if search_terms else 'ALL'
            
            # Perform search using email manager
            messages = self.email_manager.search_messages(
                folder=self.current_folder or 'INBOX',
                search_criteria=search_query,
                account_id=self.current_account_id
            )
            
            # Add messages to list
            self.message_list.add_messages(messages)
            
            self.status_message.emit(f"Found {len(messages)} messages", 3000)
            
        except Exception as e:
            self.status_message.emit(f"Search failed: {e}", 5000)
    
    def _build_date_search_term(self, date_range: str) -> Optional[str]:
        """Build IMAP date search term."""
        today = datetime.now().date()
        
        if date_range == 'Today':
            return f'SINCE "{today.strftime("%d-%b-%Y")}"'
        elif date_range == 'Yesterday':
            yesterday = today - timedelta(days=1)
            return f'ON "{yesterday.strftime("%d-%b-%Y")}"'
        elif date_range == 'This week':
            week_start = today - timedelta(days=today.weekday())
            return f'SINCE "{week_start.strftime("%d-%b-%Y")}"'
        elif date_range == 'Last week':
            week_start = today - timedelta(days=today.weekday() + 7)
            week_end = today - timedelta(days=today.weekday() + 1)
            return f'(SINCE "{week_start.strftime("%d-%b-%Y")}" BEFORE "{week_end.strftime("%d-%b-%Y")}")'
        elif date_range == 'This month':
            month_start = today.replace(day=1)
            return f'SINCE "{month_start.strftime("%d-%b-%Y")}"'
        elif date_range == 'Last month':
            if today.month == 1:
                last_month_start = today.replace(year=today.year-1, month=12, day=1)
                last_month_end = today.replace(day=1) - timedelta(days=1)
            else:
                last_month_start = today.replace(month=today.month-1, day=1)
                last_month_end = today.replace(day=1) - timedelta(days=1)
            return f'(SINCE "{last_month_start.strftime("%d-%b-%Y")}" BEFORE "{last_month_end.strftime("%d-%b-%Y")}")'
        
        return None
    
    @pyqtSlot()
    def clear_search(self):
        """Clear search and return to normal folder view."""
        self.quick_search.clear()
        if self.current_folder and self.current_account_id:
            self.load_messages()
    
    def _toggle_threading(self):
        """Toggle conversation threading."""
        self.message_list.toggle_threading()
        self.status_message.emit(
            f"Threading {'enabled' if self.message_list.show_threading else 'disabled'}", 
            2000
        ) 