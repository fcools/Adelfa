"""
Main application window for Adelfa PIM suite.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QTextEdit, QMenuBar, QMenu, QStatusBar, QToolBar, QLabel,
    QStackedWidget, QTabWidget, QPushButton
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QFont

from ..config.app_config import AppConfig
from ..utils.logging_setup import get_logger


class NavigationPane(QWidget):
    """
    Navigation pane for switching between PIM modules.
    
    Provides an Outlook-style navigation with modules for:
    - Email
    - Calendar
    - Contacts
    - Tasks
    - Notes
    """
    
    # Signal emitted when module selection changes
    module_changed = pyqtSignal(str)
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the navigation pane.
        
        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.current_module = "email"
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the navigation pane UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # Module buttons with icons and labels
        self.modules = [
            ("email", "📧 Email", "Access your email accounts"),
            ("calendar", "📅 Calendar", "Manage your calendar and events"),
            ("contacts", "👤 Contacts", "Manage your address book"),
            ("tasks", "✅ Tasks", "Organize your to-do lists"),
            ("notes", "📝 Notes", "Create and organize notes"),
        ]
        
        self.buttons = {}
        
        for module_id, label, tooltip in self.modules:
            button = QPushButton(label)
            button.setToolTip(tooltip)
            button.setCheckable(True)
            button.setFixedHeight(40)
            button.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 8px 12px;
                    border: none;
                    background-color: transparent;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #e3f2fd;
                }
                QPushButton:checked {
                    background-color: #2196f3;
                    color: white;
                    font-weight: bold;
                }
            """)
            
            # Connect button click to module change
            button.clicked.connect(lambda checked, mid=module_id: self._on_module_clicked(mid))
            
            self.buttons[module_id] = button
            layout.addWidget(button)
        
        # Set email as default selected
        self.buttons["email"].setChecked(True)
        
        # Add stretch to push buttons to top
        layout.addStretch()
        
        # Set fixed width for navigation pane
        self.setFixedWidth(150)
        self.setStyleSheet("""
            NavigationPane {
                background-color: #f5f5f5;
                border-right: 1px solid #ccc;
            }
        """)
    
    def _on_module_clicked(self, module_id: str) -> None:
        """
        Handle module button click.
        
        Args:
            module_id: ID of the clicked module.
        """
        # Update button states
        for mid, button in self.buttons.items():
            button.setChecked(mid == module_id)
        
        self.current_module = module_id
        self.module_changed.emit(module_id)


class AdelfahMainWindow(QMainWindow):
    """
    Main application window with Outlook-style interface for the PIM suite.
    
    Features:
    - Navigation pane for switching between modules (email, calendar, contacts, tasks, notes)
    - Module-specific layouts and functionality
    - Integrated toolbar and menu system
    """
    
    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None):
        """
        Initialize the main window.
        
        Args:
            config: Application configuration.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.config = config
        self.logger = get_logger(__name__)
        
        self.setWindowTitle("Adelfa PIM Suite")
        self.setMinimumSize(1000, 700)
        
        # Apply configuration
        self._apply_config()
        
        # Set up UI components
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbars()
        self._setup_status_bar()
        
        self.logger.info("Main window initialized")
    
    def _apply_config(self) -> None:
        """Apply configuration settings to the window."""
        # Set window size
        self.resize(self.config.ui.window_width, self.config.ui.window_height)
        
        # Set default font
        font = QFont(self.config.ui.font_family, self.config.ui.font_size)
        self.setFont(font)
    
    def _setup_ui(self) -> None:
        """Set up the main UI layout."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create navigation pane
        self.navigation_pane = NavigationPane()
        self.navigation_pane.module_changed.connect(self._on_module_changed)
        main_layout.addWidget(self.navigation_pane)
        
        # Create stacked widget for different module views
        self.module_stack = QStackedWidget()
        main_layout.addWidget(self.module_stack)
        
        # Create module views
        self._create_email_view()
        self._create_calendar_view()
        self._create_contacts_view()
        self._create_tasks_view()
        self._create_notes_view()
        
        # Set email view as default
        self.module_stack.setCurrentIndex(0)
    
    def _create_email_view(self) -> None:
        """Create the email module view."""
        email_widget = QWidget()
        layout = QHBoxLayout(email_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create 3-pane email layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left pane: Folder tree
        self.folder_tree = self._create_folder_tree()
        splitter.addWidget(self.folder_tree)
        
        # Right splitter for message list and preview
        right_splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(right_splitter)
        
        # Center pane: Message list
        self.message_list = self._create_message_list()
        right_splitter.addWidget(self.message_list)
        
        # Right pane: Message preview (if enabled)
        if self.config.ui.show_preview_pane:
            self.message_preview = self._create_message_preview()
            right_splitter.addWidget(self.message_preview)
            right_splitter.setSizes([400, 300])
        
        # Set initial splitter sizes
        splitter.setSizes([200, 800])
        
        self.module_stack.addWidget(email_widget)
    
    def _create_calendar_view(self) -> None:
        """Create the calendar module view."""
        calendar_widget = QWidget()
        layout = QVBoxLayout(calendar_widget)
        
        # Placeholder calendar view
        calendar_label = QLabel("📅 Calendar View")
        calendar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        calendar_label.setStyleSheet("font-size: 24px; color: #666; padding: 50px;")
        layout.addWidget(calendar_label)
        
        # Add placeholder content
        placeholder = QLabel("Calendar functionality will be implemented here.\n\n"
                            "Features will include:\n"
                            "• Day, Week, Month, and Year views\n"
                            "• Event creation and editing\n"
                            "• CalDAV synchronization\n"
                            "• Meeting invitations\n"
                            "• Recurring events")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(placeholder)
        
        self.module_stack.addWidget(calendar_widget)
    
    def _create_contacts_view(self) -> None:
        """Create the contacts module view."""
        contacts_widget = QWidget()
        layout = QVBoxLayout(contacts_widget)
        
        # Placeholder contacts view
        contacts_label = QLabel("👤 Contacts View")
        contacts_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contacts_label.setStyleSheet("font-size: 24px; color: #666; padding: 50px;")
        layout.addWidget(contacts_label)
        
        # Add placeholder content
        placeholder = QLabel("Contacts functionality will be implemented here.\n\n"
                            "Features will include:\n"
                            "• Contact creation and editing\n"
                            "• Groups and categories\n"
                            "• CardDAV synchronization\n"
                            "• Photo management\n"
                            "• Import/export vCard files")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(placeholder)
        
        self.module_stack.addWidget(contacts_widget)
    
    def _create_tasks_view(self) -> None:
        """Create the tasks module view."""
        tasks_widget = QWidget()
        layout = QVBoxLayout(tasks_widget)
        
        # Placeholder tasks view
        tasks_label = QLabel("✅ Tasks View")
        tasks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tasks_label.setStyleSheet("font-size: 24px; color: #666; padding: 50px;")
        layout.addWidget(tasks_label)
        
        # Add placeholder content
        placeholder = QLabel("Tasks functionality will be implemented here.\n\n"
                            "Features will include:\n"
                            "• To-do lists and projects\n"
                            "• Priority and due dates\n"
                            "• Task synchronization\n"
                            "• Progress tracking\n"
                            "• Categories and tags")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(placeholder)
        
        self.module_stack.addWidget(tasks_widget)
    
    def _create_notes_view(self) -> None:
        """Create the notes module view."""
        notes_widget = QWidget()
        layout = QVBoxLayout(notes_widget)
        
        # Placeholder notes view
        notes_label = QLabel("📝 Notes View")
        notes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notes_label.setStyleSheet("font-size: 24px; color: #666; padding: 50px;")
        layout.addWidget(notes_label)
        
        # Add placeholder content
        placeholder = QLabel("Notes functionality will be implemented here.\n\n"
                            "Features will include:\n"
                            "• Rich text notes\n"
                            "• Notebooks and organization\n"
                            "• Tags and search\n"
                            "• Attachments\n"
                            "• Cloud synchronization")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(placeholder)
        
        self.module_stack.addWidget(notes_widget)
    
    def _on_module_changed(self, module_id: str) -> None:
        """
        Handle module change from navigation pane.
        
        Args:
            module_id: ID of the selected module.
        """
        module_index = {
            "email": 0,
            "calendar": 1,
            "contacts": 2,
            "tasks": 3,
            "notes": 4,
        }.get(module_id, 0)
        
        self.module_stack.setCurrentIndex(module_index)
        self.logger.info(f"Switched to {module_id} module")
        
        # Update window title
        module_names = {
            "email": "Email",
            "calendar": "Calendar",
            "contacts": "Contacts", 
            "tasks": "Tasks",
            "notes": "Notes",
        }
        module_name = module_names.get(module_id, "Email")
        self.setWindowTitle(f"Adelfa PIM Suite - {module_name}")
    
    def _create_folder_tree(self) -> QTreeWidget:
        """
        Create the folder tree widget.
        
        Returns:
            QTreeWidget: Configured folder tree.
        """
        tree = QTreeWidget()
        tree.setHeaderLabel("Folders")
        tree.setMaximumWidth(250)
        tree.setMinimumWidth(150)
        
        # Add default folders (Outlook-style)
        inbox = QTreeWidgetItem(tree, ["📥 Inbox"])
        inbox.setData(0, Qt.ItemDataRole.UserRole, "INBOX")
        
        sent = QTreeWidgetItem(tree, ["📤 Sent Items"])
        sent.setData(0, Qt.ItemDataRole.UserRole, "SENT")
        
        drafts = QTreeWidgetItem(tree, ["📝 Drafts"])
        drafts.setData(0, Qt.ItemDataRole.UserRole, "DRAFTS")
        
        deleted = QTreeWidgetItem(tree, ["🗑️ Deleted Items"])
        deleted.setData(0, Qt.ItemDataRole.UserRole, "TRASH")
        
        junk = QTreeWidgetItem(tree, ["🚫 Junk Email"])
        junk.setData(0, Qt.ItemDataRole.UserRole, "SPAM")
        
        # Expand all by default
        tree.expandAll()
        
        # Select Inbox by default
        tree.setCurrentItem(inbox)
        
        return tree
    
    def _create_message_list(self) -> QListWidget:
        """
        Create the message list widget.
        
        Returns:
            QListWidget: Configured message list.
        """
        list_widget = QListWidget()
        
        # Add some placeholder messages for demonstration
        for i in range(5):
            item = QListWidgetItem(f"📧 Sample Email {i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, f"email_{i + 1}")
            list_widget.addItem(item)
        
        return list_widget
    
    def _create_message_preview(self) -> QTextEdit:
        """
        Create the message preview widget.
        
        Returns:
            QTextEdit: Configured message preview.
        """
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlaceholderText("Select a message to preview...")
        
        # Set some sample content
        preview.setHtml("""
        <h3>Welcome to Adelfa Email Client!</h3>
        <p>This is the message preview pane. When you select an email from the message list, 
        its content will be displayed here.</p>
        <p><strong>Key Features:</strong></p>
        <ul>
            <li>Outlook 365-style interface</li>
            <li>Point-size font selection</li>
            <li>Rich text editing</li>
            <li>Conversation threading</li>
            <li>Cross-platform compatibility</li>
        </ul>
        <p><em>Start by setting up your email account in the File menu.</em></p>
        """)
        
        return preview
    
    def _setup_menus(self) -> None:
        """Set up the application menu bar."""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("File")
        
        # New submenu
        new_menu = file_menu.addMenu("New")
        
        new_email_action = QAction("Email", self)
        new_email_action.setShortcut("Ctrl+N")
        new_menu.addAction(new_email_action)
        
        new_event_action = QAction("Calendar Event", self)
        new_event_action.setShortcut("Ctrl+Shift+E")
        new_menu.addAction(new_event_action)
        
        new_contact_action = QAction("Contact", self)
        new_contact_action.setShortcut("Ctrl+Shift+C")
        new_menu.addAction(new_contact_action)
        
        new_task_action = QAction("Task", self)
        new_task_action.setShortcut("Ctrl+Shift+T")
        new_menu.addAction(new_task_action)
        
        new_note_action = QAction("Note", self)
        new_note_action.setShortcut("Ctrl+Shift+N")
        new_menu.addAction(new_note_action)
        
        file_menu.addSeparator()
        
        # Import/Export submenu
        import_export_menu = file_menu.addMenu("Import/Export")
        
        import_pst_action = QAction("Import Outlook PST...", self)
        import_export_menu.addAction(import_pst_action)
        
        import_ics_action = QAction("Import Calendar (ICS)...", self)
        import_export_menu.addAction(import_ics_action)
        
        import_vcf_action = QAction("Import Contacts (vCard)...", self)
        import_export_menu.addAction(import_vcf_action)
        
        import_export_menu.addSeparator()
        
        export_calendar_action = QAction("Export Calendar...", self)
        import_export_menu.addAction(export_calendar_action)
        
        export_contacts_action = QAction("Export Contacts...", self)
        import_export_menu.addAction(export_contacts_action)
        
        file_menu.addSeparator()
        
        # Account management
        add_account_action = QAction("Add Account...", self)
        file_menu.addAction(add_account_action)
        
        account_settings_action = QAction("Account Settings...", self)
        file_menu.addAction(account_settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        edit_menu = menubar.addMenu("Edit")
        
        # Standard edit actions
        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Y")
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        cut_action = QAction("Cut", self)
        cut_action.setShortcut("Ctrl+X")
        edit_menu.addAction(cut_action)
        
        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        edit_menu.addAction(copy_action)
        
        paste_action = QAction("Paste", self)
        paste_action.setShortcut("Ctrl+V")
        edit_menu.addAction(paste_action)
        
        edit_menu.addSeparator()
        
        select_all_action = QAction("Select All", self)
        select_all_action.setShortcut("Ctrl+A")
        edit_menu.addAction(select_all_action)
        
        edit_menu.addSeparator()
        
        find_action = QAction("Find...", self)
        find_action.setShortcut("Ctrl+F")
        edit_menu.addAction(find_action)
        
        edit_menu.addSeparator()
        
        preferences_action = QAction("Preferences...", self)
        preferences_action.setShortcut("Ctrl+,")
        edit_menu.addAction(preferences_action)
        
        # View Menu
        view_menu = menubar.addMenu("View")
        
        # Module switching
        modules_menu = view_menu.addMenu("Go to Module")
        
        email_module_action = QAction("Email", self)
        email_module_action.setShortcut("Ctrl+1")
        email_module_action.triggered.connect(lambda: self.navigation_pane._on_module_clicked("email"))
        modules_menu.addAction(email_module_action)
        
        calendar_module_action = QAction("Calendar", self)
        calendar_module_action.setShortcut("Ctrl+2")
        calendar_module_action.triggered.connect(lambda: self.navigation_pane._on_module_clicked("calendar"))
        modules_menu.addAction(calendar_module_action)
        
        contacts_module_action = QAction("Contacts", self)
        contacts_module_action.setShortcut("Ctrl+3")
        contacts_module_action.triggered.connect(lambda: self.navigation_pane._on_module_clicked("contacts"))
        modules_menu.addAction(contacts_module_action)
        
        tasks_module_action = QAction("Tasks", self)
        tasks_module_action.setShortcut("Ctrl+4")
        tasks_module_action.triggered.connect(lambda: self.navigation_pane._on_module_clicked("tasks"))
        modules_menu.addAction(tasks_module_action)
        
        notes_module_action = QAction("Notes", self)
        notes_module_action.setShortcut("Ctrl+5")
        notes_module_action.triggered.connect(lambda: self.navigation_pane._on_module_clicked("notes"))
        modules_menu.addAction(notes_module_action)
        
        view_menu.addSeparator()
        
        # View options
        toggle_navigation_action = QAction("Toggle Navigation Pane", self)
        toggle_navigation_action.setShortcut("F9")
        view_menu.addAction(toggle_navigation_action)
        
        toggle_preview_action = QAction("Toggle Preview Pane", self)
        toggle_preview_action.setShortcut("F3")
        view_menu.addAction(toggle_preview_action)
        
        view_menu.addSeparator()
        
        # View modes
        view_modes_menu = view_menu.addMenu("View Mode")
        
        normal_view_action = QAction("Normal", self)
        view_modes_menu.addAction(normal_view_action)
        
        reading_view_action = QAction("Reading View", self)
        view_modes_menu.addAction(reading_view_action)
        
        # Tools Menu
        tools_menu = menubar.addMenu("Tools")
        
        sync_action = QAction("Synchronize All", self)
        sync_action.setShortcut("F9")
        tools_menu.addAction(sync_action)
        
        tools_menu.addSeparator()
        
        rules_action = QAction("Rules and Filters...", self)
        tools_menu.addAction(rules_action)
        
        signatures_action = QAction("Signatures...", self)
        tools_menu.addAction(signatures_action)
        
        tools_menu.addSeparator()
        
        data_export_action = QAction("Export Data...", self)
        tools_menu.addAction(data_export_action)
        
        cleanup_action = QAction("Cleanup Tools...", self)
        tools_menu.addAction(cleanup_action)
        
        # Help Menu
        help_menu = menubar.addMenu("Help")
        
        help_action = QAction("Help", self)
        help_action.setShortcut("F1")
        help_menu.addAction(help_action)
        
        keyboard_shortcuts_action = QAction("Keyboard Shortcuts", self)
        help_menu.addAction(keyboard_shortcuts_action)
        
        help_menu.addSeparator()
        
        check_updates_action = QAction("Check for Updates...", self)
        help_menu.addAction(check_updates_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("About Adelfa", self)
        help_menu.addAction(about_action)
    
    def _setup_toolbars(self) -> None:
        """Set up the application toolbars."""
        # Main toolbar
        main_toolbar = self.addToolBar("Main")
        main_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        
        # New Email button
        new_email_action = QAction("New Email", self)
        new_email_action.setShortcut("Ctrl+N")
        new_email_action.setToolTip("Compose a new email (Ctrl+N)")
        main_toolbar.addAction(new_email_action)
        
        main_toolbar.addSeparator()
        
        # Reply buttons
        reply_action = QAction("Reply", self)
        reply_action.setShortcut("Ctrl+R")
        main_toolbar.addAction(reply_action)
        
        reply_all_action = QAction("Reply All", self)
        reply_all_action.setShortcut("Ctrl+Shift+R")
        main_toolbar.addAction(reply_all_action)
        
        forward_action = QAction("Forward", self)
        forward_action.setShortcut("Ctrl+F")
        main_toolbar.addAction(forward_action)
        
        main_toolbar.addSeparator()
        
        # Delete button
        delete_action = QAction("Delete", self)
        delete_action.setShortcut("Delete")
        main_toolbar.addAction(delete_action)
    
    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        status_bar = self.statusBar()
        
        # Connection status
        self.connection_status = QLabel("Not connected")
        status_bar.addWidget(self.connection_status)
        
        status_bar.addPermanentWidget(QLabel("Adelfa Email Client v0.1.0-dev")) 