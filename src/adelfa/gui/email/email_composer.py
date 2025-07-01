"""
Email composition window for Adelfa PIM suite.

Provides rich text email composition with Outlook-style formatting,
attachment support, and send functionality.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QToolBar, QComboBox, QSpinBox, QFileDialog,
    QListWidget, QListWidgetItem, QFrame, QSplitter, QCheckBox, QGroupBox,
    QMessageBox, QProgressBar, QStatusBar, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QFontDatabase, QColor, QPalette, QTextCursor,
    QTextCharFormat, QTextBlockFormat, QTextListFormat, QKeySequence
)
from typing import List, Optional, Dict, Any
import os
import mimetypes
from pathlib import Path
import html

from ...core.email.smtp_client import OutgoingEmail, EmailAddress, EmailAttachment
from ...core.email.email_manager import EmailManager
from ...data.models.accounts import Account
from ...utils.i18n import _


class RichTextEditor(QTextEdit):
    """Rich text editor with Outlook-style formatting capabilities."""
    
    def __init__(self):
        super().__init__()
        self.setup_editor()
    
    def setup_editor(self):
        """Setup the rich text editor."""
        # Set default font
        default_font = QFont("Segoe UI", 11)
        self.setFont(default_font)
        self.setFontFamily("Segoe UI")
        self.setFontPointSize(11)
        
        # Enable rich text
        self.setAcceptRichText(True)
        
        # Set minimum size
        self.setMinimumHeight(300)
    
    def insert_signature(self, signature: str):
        """Insert email signature at the current cursor position."""
        if signature:
            cursor = self.textCursor()
            cursor.insertHtml(f"<br><br>-- <br>{signature}")
    
    def get_html_content(self) -> str:
        """Get the HTML content of the editor."""
        return self.toHtml()
    
    def get_plain_text_content(self) -> str:
        """Get the plain text content of the editor."""
        return self.toPlainText()


class AttachmentListWidget(QListWidget):
    """Widget for managing email attachments."""
    
    attachment_removed = pyqtSignal(str)  # filename
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.attachments: Dict[str, EmailAttachment] = {}
    
    def setup_ui(self):
        """Setup the attachment list UI."""
        self.setMaximumHeight(120)
        self.setAlternatingRowColors(True)
    
    def add_attachment(self, filepath: str):
        """Add an attachment to the list."""
        if filepath in self.attachments:
            return  # Already added
        
        try:
            file_path = Path(filepath)
            if not file_path.exists():
                QMessageBox.warning(self, "Error", f"File not found: {filepath}")
                return
            
            # Create attachment
            attachment = EmailAttachment(
                filename=file_path.name,
                filepath=filepath
            )
            
            # Add to list
            item = QListWidgetItem(f"📎 {file_path.name} ({self._format_size(file_path.stat().st_size)})")
            item.setData(Qt.ItemDataRole.UserRole, filepath)
            
            self.addItem(item)
            self.attachments[filepath] = attachment
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to add attachment: {e}")
    
    def remove_selected_attachment(self):
        """Remove the selected attachment."""
        current_item = self.currentItem()
        if current_item:
            filepath = current_item.data(Qt.ItemDataRole.UserRole)
            if filepath in self.attachments:
                del self.attachments[filepath]
                self.takeItem(self.row(current_item))
                self.attachment_removed.emit(filepath)
    
    def get_attachments(self) -> List[EmailAttachment]:
        """Get all attachments."""
        return list(self.attachments.values())
    
    def clear_attachments(self):
        """Clear all attachments."""
        self.clear()
        self.attachments.clear()
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Delete:
            self.remove_selected_attachment()
        else:
            super().keyPressEvent(event)


class EmailComposer(QDialog):
    """
    Email composition dialog.
    
    Provides rich text email composition with formatting tools,
    attachment support, and sending functionality.
    """
    
    email_sent = pyqtSignal(bool)  # success
    
    def __init__(self, email_manager: EmailManager, accounts: List[Account], 
                 reply_to_message=None, parent=None):
        super().__init__(parent)
        self.email_manager = email_manager
        self.accounts = accounts
        self.reply_to_message = reply_to_message
        self.default_account = accounts[0] if accounts else None
        
        self.setup_ui()
        self.setup_toolbar()
        self.setup_connections()
        
        # Setup for reply if needed
        if reply_to_message:
            self.setup_reply()
    
    def setup_ui(self):
        """Setup the composer UI."""
        self.setWindowTitle("Compose Email")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # Create toolbar
        self.toolbar = QToolBar()
        layout.addWidget(self.toolbar)
        
        # Create main content area
        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        
        # Header section (To, CC, BCC, Subject)
        self.setup_header_section(content_layout)
        
        # Main editor area
        editor_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Rich text editor
        self.editor = RichTextEditor()
        editor_splitter.addWidget(self.editor)
        
        # Attachment area
        attachment_frame = QFrame()
        attachment_layout = QVBoxLayout(attachment_frame)
        attachment_layout.setContentsMargins(5, 5, 5, 5)
        
        attachment_label = QLabel("Attachments:")
        attachment_layout.addWidget(attachment_label)
        
        self.attachment_list = AttachmentListWidget()
        attachment_layout.addWidget(self.attachment_list)
        
        attachment_buttons = QHBoxLayout()
        
        add_attachment_btn = QPushButton("Add File...")
        add_attachment_btn.clicked.connect(self.add_attachment)
        attachment_buttons.addWidget(add_attachment_btn)
        
        remove_attachment_btn = QPushButton("Remove")
        remove_attachment_btn.clicked.connect(self.attachment_list.remove_selected_attachment)
        attachment_buttons.addWidget(remove_attachment_btn)
        
        attachment_buttons.addStretch()
        attachment_layout.addLayout(attachment_buttons)
        
        editor_splitter.addWidget(attachment_frame)
        editor_splitter.setSizes([500, 150])
        
        content_layout.addWidget(editor_splitter)
        
        layout.addWidget(content_frame)
        
        # Button area
        button_layout = QHBoxLayout()
        
        self.send_button = QPushButton("Send")
        self.send_button.setDefault(True)
        self.send_button.clicked.connect(self.send_email)
        button_layout.addWidget(self.send_button)
        
        save_draft_button = QPushButton("Save Draft")
        save_draft_button.clicked.connect(self.save_draft)
        button_layout.addWidget(save_draft_button)
        
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)
    
    def setup_header_section(self, layout):
        """Setup the email header section (To, CC, Subject, etc.)."""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_layout = QGridLayout(header_frame)
        
        # Account selection
        header_layout.addWidget(QLabel("From:"), 0, 0)
        self.from_combo = QComboBox()
        for account in self.accounts:
            self.from_combo.addItem(f"{account.display_name} <{account.email_address}>", account)
        header_layout.addWidget(self.from_combo, 0, 1)
        
        # To field
        header_layout.addWidget(QLabel("To:"), 1, 0)
        self.to_edit = QLineEdit()
        self.to_edit.setPlaceholderText("Enter recipients separated by commas")
        header_layout.addWidget(self.to_edit, 1, 1)
        
        # CC field
        header_layout.addWidget(QLabel("Cc:"), 2, 0)
        self.cc_edit = QLineEdit()
        self.cc_edit.setPlaceholderText("Carbon copy recipients")
        header_layout.addWidget(self.cc_edit, 2, 1)
        
        # BCC field
        header_layout.addWidget(QLabel("Bcc:"), 3, 0)
        self.bcc_edit = QLineEdit()
        self.bcc_edit.setPlaceholderText("Blind carbon copy recipients")
        header_layout.addWidget(self.bcc_edit, 3, 1)
        
        # Subject field
        header_layout.addWidget(QLabel("Subject:"), 4, 0)
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("Enter email subject")
        header_layout.addWidget(self.subject_edit, 4, 1)
        
        # Options
        options_layout = QHBoxLayout()
        
        self.high_priority_check = QCheckBox("High Priority")
        options_layout.addWidget(self.high_priority_check)
        
        self.request_receipt_check = QCheckBox("Request Read Receipt")
        options_layout.addWidget(self.request_receipt_check)
        
        options_layout.addStretch()
        
        header_layout.addLayout(options_layout, 5, 1)
        
        layout.addWidget(header_frame)
    
    def setup_toolbar(self):
        """Setup the formatting toolbar."""
        # Font family
        font_family_combo = QComboBox()
        font_families = ["Segoe UI", "Arial", "Times New Roman", "Calibri", "Helvetica", "Georgia", "Verdana"]
        font_family_combo.addItems(font_families)
        font_family_combo.setCurrentText("Segoe UI")
        font_family_combo.currentTextChanged.connect(self.change_font_family)
        self.toolbar.addWidget(QLabel("Font:"))
        self.toolbar.addWidget(font_family_combo)
        
        # Font size
        font_size_combo = QComboBox()
        font_sizes = ["8", "9", "10", "11", "12", "14", "16", "18", "20", "24", "28", "32", "36", "48", "72"]
        font_size_combo.addItems(font_sizes)
        font_size_combo.setCurrentText("11")
        font_size_combo.currentTextChanged.connect(self.change_font_size)
        self.toolbar.addWidget(font_size_combo)
        
        self.toolbar.addSeparator()
        
        # Bold, Italic, Underline
        bold_action = QAction("B", self)
        bold_action.setCheckable(True)
        bold_action.setShortcut(QKeySequence.StandardKey.Bold)
        bold_action.triggered.connect(lambda: self.editor.setFontWeight(QFont.Weight.Bold if bold_action.isChecked() else QFont.Weight.Normal))
        self.toolbar.addAction(bold_action)
        
        italic_action = QAction("I", self)
        italic_action.setCheckable(True)
        italic_action.setShortcut(QKeySequence.StandardKey.Italic)
        italic_action.triggered.connect(self.editor.setFontItalic)
        self.toolbar.addAction(italic_action)
        
        underline_action = QAction("U", self)
        underline_action.setCheckable(True)
        underline_action.setShortcut(QKeySequence.StandardKey.Underline)
        underline_action.triggered.connect(self.editor.setFontUnderline)
        self.toolbar.addAction(underline_action)
        
        self.toolbar.addSeparator()
        
        # Text color
        text_color_action = QAction("A", self)
        text_color_action.triggered.connect(self.change_text_color)
        self.toolbar.addAction(text_color_action)
        
        self.toolbar.addSeparator()
        
        # Alignment
        align_left_action = QAction("⬅", self)
        align_left_action.triggered.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignLeft))
        self.toolbar.addAction(align_left_action)
        
        align_center_action = QAction("⬝", self)
        align_center_action.triggered.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignCenter))
        self.toolbar.addAction(align_center_action)
        
        align_right_action = QAction("➡", self)
        align_right_action.triggered.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignRight))
        self.toolbar.addAction(align_right_action)
        
        self.toolbar.addSeparator()
        
        # Lists
        bullet_list_action = QAction("• List", self)
        bullet_list_action.triggered.connect(self.insert_bullet_list)
        self.toolbar.addAction(bullet_list_action)
        
        numbered_list_action = QAction("1. List", self)
        numbered_list_action.triggered.connect(self.insert_numbered_list)
        self.toolbar.addAction(numbered_list_action)
    
    def setup_connections(self):
        """Setup signal connections."""
        # Auto-save draft every 2 minutes
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_draft)
        self.auto_save_timer.start(120000)  # 2 minutes
    
    def setup_reply(self):
        """Setup the composer for replying to a message."""
        if not self.reply_to_message:
            return
        
        # Set To field
        self.to_edit.setText(self.reply_to_message.headers.from_addr)
        
        # Set subject with "Re: " prefix
        original_subject = self.reply_to_message.headers.subject or ""
        if not original_subject.startswith("Re: "):
            reply_subject = f"Re: {original_subject}"
        else:
            reply_subject = original_subject
        self.subject_edit.setText(reply_subject)
        
        # Create quoted content
        quoted_content = self.create_quoted_content(self.reply_to_message)
        self.editor.setHtml(quoted_content)
        
        # Position cursor at the beginning
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        self.editor.setTextCursor(cursor)
    
    def create_quoted_content(self, message) -> str:
        """Create quoted content for reply."""
        date_str = message.headers.date.strftime("%A, %B %d, %Y at %I:%M %p")
        
        quoted_html = f"""
        <br><br>
        <div style="border-left: 2px solid #0078d4; padding-left: 10px; margin: 10px 0; color: #666;">
            <p><strong>From:</strong> {html.escape(message.headers.from_addr)}<br>
            <strong>Date:</strong> {date_str}<br>
            <strong>Subject:</strong> {html.escape(message.headers.subject or "")}</p>
            
            <div style="margin-top: 10px;">
                {message.html_content or html.escape(message.text_content or "")}
            </div>
        </div>
        """
        
        return quoted_html
    
    def change_font_family(self, family: str):
        """Change font family for selected text."""
        self.editor.setFontFamily(family)
    
    def change_font_size(self, size: str):
        """Change font size for selected text."""
        try:
            self.editor.setFontPointSize(int(size))
        except ValueError:
            pass
    
    def change_text_color(self):
        """Change text color for selected text."""
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(Qt.GlobalColor.black, self)
        if color.isValid():
            self.editor.setTextColor(color)
    
    def insert_bullet_list(self):
        """Insert a bullet list."""
        cursor = self.editor.textCursor()
        list_format = QTextListFormat()
        list_format.setStyle(QTextListFormat.Style.ListDisc)
        cursor.insertList(list_format)
    
    def insert_numbered_list(self):
        """Insert a numbered list."""
        cursor = self.editor.textCursor()
        list_format = QTextListFormat()
        list_format.setStyle(QTextListFormat.Style.ListDecimal)
        cursor.insertList(list_format)
    
    def add_attachment(self):
        """Add file attachment."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Attach",
            "",
            "All Files (*.*)"
        )
        
        for file_path in file_paths:
            self.attachment_list.add_attachment(file_path)
    
    def validate_email_addresses(self, addresses: str) -> List[EmailAddress]:
        """Validate and parse email addresses."""
        if not addresses.strip():
            return []
        
        email_list = []
        for addr in addresses.split(','):
            addr = addr.strip()
            if addr:
                # Simple email validation
                if '@' in addr and '.' in addr.split('@')[1]:
                    email_list.append(EmailAddress(email=addr))
                else:
                    raise ValueError(f"Invalid email address: {addr}")
        
        return email_list
    
    def send_email(self):
        """Send the email."""
        try:
            # Validate fields
            if not self.subject_edit.text().strip():
                QMessageBox.warning(self, "Error", "Please enter a subject.")
                return
            
            to_addresses = self.validate_email_addresses(self.to_edit.text())
            if not to_addresses:
                QMessageBox.warning(self, "Error", "Please enter at least one recipient.")
                return
            
            cc_addresses = self.validate_email_addresses(self.cc_edit.text())
            bcc_addresses = self.validate_email_addresses(self.bcc_edit.text())
            
            # Get selected account
            selected_account = self.from_combo.currentData()
            if not selected_account:
                QMessageBox.warning(self, "Error", "No account selected.")
                return
            
            # Create outgoing email
            email = OutgoingEmail(
                subject=self.subject_edit.text(),
                from_addr=EmailAddress(
                    email=selected_account.email_address,
                    name=selected_account.display_name
                ),
                to_addrs=to_addresses,
                cc_addrs=cc_addresses,
                bcc_addrs=bcc_addresses,
                html_content=self.editor.get_html_content(),
                text_content=self.editor.get_plain_text_content(),
                attachments=self.attachment_list.get_attachments(),
                priority='high' if self.high_priority_check.isChecked() else 'normal',
                request_receipt=self.request_receipt_check.isChecked()
            )
            
            # Disable send button and show progress
            self.send_button.setEnabled(False)
            self.send_button.setText("Sending...")
            self.status_bar.showMessage("Sending email...")
            
            # Send email
            success = self.email_manager.send_email(email, selected_account.id)
            
            if success:
                self.status_bar.showMessage("Email sent successfully!")
                QMessageBox.information(self, "Success", "Email sent successfully!")
                self.email_sent.emit(True)
                self.accept()
            else:
                self.status_bar.showMessage("Failed to send email")
                QMessageBox.warning(self, "Error", "Failed to send email. Please check your connection and try again.")
                self.email_sent.emit(False)
            
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while sending: {e}")
            self.email_sent.emit(False)
        finally:
            self.send_button.setEnabled(True)
            self.send_button.setText("Send")
    
    def save_draft(self):
        """Save email as draft."""
        # TODO: Implement draft saving
        self.status_bar.showMessage("Save draft (not implemented yet)")
    
    def auto_save_draft(self):
        """Auto-save draft."""
        # Only auto-save if there's content
        if (self.subject_edit.text().strip() or 
            self.to_edit.text().strip() or 
            self.editor.toPlainText().strip()):
            self.save_draft()
    
    def closeEvent(self, event):
        """Handle close event."""
        # Check if there are unsaved changes
        if (self.subject_edit.text().strip() or 
            self.to_edit.text().strip() or 
            self.editor.toPlainText().strip()):
            
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save as draft before closing?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self.save_draft()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept() 