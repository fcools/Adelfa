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
from ..utils.i18n import _
from ..core.email.account_manager import AccountManager
from ..core.email.email_manager import EmailManager
from ..core.email.credential_manager import CredentialManager
from ..data.repositories.account_repository import AccountRepository
from .email.email_view import EmailView
from .email.email_composer import EmailComposer
from .email.account_manager_dialog import AccountManagerDialog


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
    
    def __init__(self, config: AppConfig, db_session=None, parent: Optional[QWidget] = None):
        """
        Initialize the main window.
        
        Args:
            config: Application configuration.
            db_session: Database session for account management.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize core components
        self.credential_manager = CredentialManager()
        self.account_repository = AccountRepository(db_session)
        self.account_manager = AccountManager(db_session)
        self.email_manager = EmailManager(self.credential_manager, db_session)
        
        self.setWindowTitle(_("main_window.title"))
        self.setMinimumSize(1000, 700)
        
        # Apply configuration
        self._apply_config()
        
        # Set up UI components
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbars()
        self._setup_status_bar()
        
        # Load accounts and setup email
        self._load_accounts()
        self._setup_email_accounts()
        
        # Ensure initial module state is synchronized
        self._synchronize_initial_state()
        
        # Apply initial preview pane position from config
        self._update_preview_pane_menu()
        
        self.logger.info("Main window initialized")
    
    def _synchronize_initial_state(self) -> None:
        """Synchronize the initial navigation state."""
        # Trigger the module change to ensure everything is synchronized
        initial_module = self.navigation_pane.current_module
        self._on_module_changed(initial_module)
    
    def _apply_config(self) -> None:
        """Apply configuration settings to the window."""
        # Note: Window size is handled by showMaximized() in main.py
        # If not maximized, the window will use the default minimumSize of 1000x700
        
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
        # Import EmailView here to avoid circular imports
        from .email.email_view import EmailView
        
        self.email_widget = EmailView(self.email_manager)
        # Set config for column width persistence
        self.email_widget.set_config(self.config)
        # Connect email view status messages to main window status bar
        self.email_widget.status_message.connect(self.statusBar().showMessage)
        self.module_stack.addWidget(self.email_widget)
    
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
        self.setWindowTitle(f"Adelfa Personal Information Manager - {module_name}")
    
    def _set_preview_pane_position(self, position: str) -> None:
        """
        Set the preview pane position.
        
        Args:
            position: Position of preview pane: 'off', 'right', or 'bottom'
        """
        if hasattr(self, 'email_widget') and self.email_widget:
            self.email_widget.set_preview_pane_position(position)
            
        # Update config
        self.config.ui.preview_pane_position = position
        self.config.save()
        
        # Update menu state
        self.preview_off_action.setChecked(position == "off")
        self.preview_right_action.setChecked(position == "right")
        self.preview_bottom_action.setChecked(position == "bottom")
    
    def _update_preview_pane_menu(self) -> None:
        """Update preview pane menu state from config."""
        position = self.config.ui.preview_pane_position
        
        # Check if menu actions exist before updating them
        if hasattr(self, 'preview_off_action'):
            self.preview_off_action.setChecked(position == "off")
            self.preview_right_action.setChecked(position == "right")
            self.preview_bottom_action.setChecked(position == "bottom")
        
        # Apply the position to email view if it exists (without saving to avoid double-save)
        if hasattr(self, 'email_widget') and self.email_widget:
            self.email_widget._apply_preview_pane_position(position)
    
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
        list_widget.setPlaceholderText(_("main_window.placeholders.select_folder"))
        return list_widget
    
    def _create_message_preview(self) -> QTextEdit:
        """
        Create the message preview widget.
        
        Returns:
            QTextEdit: Configured message preview.
        """
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlaceholderText(_("main_window.placeholders.select_message"))
        return preview
    
    def _setup_menus(self) -> None:
        """Set up the application menu bar."""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu(_("menus.file"))
        
        # New submenu
        new_menu = file_menu.addMenu(_("menus.new"))
        
        new_email_action = QAction(_("menus.email"), self)
        new_email_action.setShortcut("Ctrl+N")
        new_menu.addAction(new_email_action)
        
        new_event_action = QAction(_("menus.calendar_event"), self)
        new_event_action.setShortcut("Ctrl+Shift+E")
        new_menu.addAction(new_event_action)
        
        new_contact_action = QAction(_("menus.contact"), self)
        new_contact_action.setShortcut("Ctrl+Shift+C")
        new_menu.addAction(new_contact_action)
        
        new_task_action = QAction(_("menus.task"), self)
        new_task_action.setShortcut("Ctrl+Shift+T")
        new_menu.addAction(new_task_action)
        
        new_note_action = QAction(_("menus.note"), self)
        new_note_action.setShortcut("Ctrl+Shift+N")
        new_menu.addAction(new_note_action)
        
        file_menu.addSeparator()
        
        # Import/Export submenu
        import_export_menu = file_menu.addMenu(_("menus.import_export"))
        
        import_pst_action = QAction(_("menus.import_pst"), self)
        import_export_menu.addAction(import_pst_action)
        
        import_ics_action = QAction(_("menus.import_ics"), self)
        import_export_menu.addAction(import_ics_action)
        
        import_vcf_action = QAction(_("menus.import_vcf"), self)
        import_export_menu.addAction(import_vcf_action)
        
        import_export_menu.addSeparator()
        
        export_calendar_action = QAction(_("menus.export_calendar"), self)
        import_export_menu.addAction(export_calendar_action)
        
        export_contacts_action = QAction(_("menus.export_contacts"), self)
        import_export_menu.addAction(export_contacts_action)
        
        file_menu.addSeparator()
        
        # Account management
        add_account_action = QAction(_("menus.add_account"), self)
        add_account_action.triggered.connect(self._on_add_account)
        file_menu.addAction(add_account_action)
        
        account_manager_action = QAction(_("menus.account_manager"), self)
        account_manager_action.triggered.connect(self._on_account_manager)
        file_menu.addAction(account_manager_action)
        
        account_settings_action = QAction(_("menus.account_settings"), self)
        account_settings_action.triggered.connect(self._on_account_settings)
        file_menu.addAction(account_settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction(_("menus.exit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        edit_menu = menubar.addMenu(_("menus.edit"))
        
        undo_action = QAction(_("menus.undo"), self)
        undo_action.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_action)
        
        redo_action = QAction(_("menus.redo"), self)
        redo_action.setShortcut("Ctrl+Y")
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        cut_action = QAction(_("menus.cut"), self)
        cut_action.setShortcut("Ctrl+X")
        edit_menu.addAction(cut_action)
        
        copy_action = QAction(_("menus.copy"), self)
        copy_action.setShortcut("Ctrl+C")
        edit_menu.addAction(copy_action)
        
        paste_action = QAction(_("menus.paste"), self)
        paste_action.setShortcut("Ctrl+V")
        edit_menu.addAction(paste_action)
        
        edit_menu.addSeparator()
        
        find_action = QAction(_("menus.find"), self)
        find_action.setShortcut("Ctrl+F")
        edit_menu.addAction(find_action)
        
        edit_menu.addSeparator()
        
        preferences_action = QAction(_("menus.preferences"), self)
        preferences_action.setShortcut("Ctrl+,")
        edit_menu.addAction(preferences_action)
        
        # View Menu
        view_menu = menubar.addMenu(_("menus.view"))
        
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
        
        # Preview pane submenu
        preview_pane_menu = view_menu.addMenu(_("menus.preview_pane"))
        
        # Create action group for radio button behavior
        from PyQt6.QtGui import QActionGroup
        self.preview_pane_group = QActionGroup(self)
        
        self.preview_off_action = QAction(_("menus.off"), self)
        self.preview_off_action.setCheckable(True)
        self.preview_off_action.triggered.connect(lambda: self._set_preview_pane_position("off"))
        self.preview_pane_group.addAction(self.preview_off_action)
        preview_pane_menu.addAction(self.preview_off_action)
        
        self.preview_right_action = QAction(_("menus.right"), self)
        self.preview_right_action.setCheckable(True)
        self.preview_right_action.triggered.connect(lambda: self._set_preview_pane_position("right"))
        self.preview_pane_group.addAction(self.preview_right_action)
        preview_pane_menu.addAction(self.preview_right_action)
        
        self.preview_bottom_action = QAction(_("menus.bottom"), self)
        self.preview_bottom_action.setCheckable(True)
        self.preview_bottom_action.triggered.connect(lambda: self._set_preview_pane_position("bottom"))
        self.preview_pane_group.addAction(self.preview_bottom_action)
        preview_pane_menu.addAction(self.preview_bottom_action)
        
        view_menu.addSeparator()
        
        # View modes
        view_modes_menu = view_menu.addMenu("View Mode")
        
        normal_view_action = QAction("Normal", self)
        view_modes_menu.addAction(normal_view_action)
        
        reading_view_action = QAction("Reading View", self)
        view_modes_menu.addAction(reading_view_action)
        
        # Tools Menu
        tools_menu = menubar.addMenu(_("menus.tools"))
        
        sync_action = QAction("Synchronize All", self)
        sync_action.setShortcut("F9")
        tools_menu.addAction(sync_action)
        
        tools_menu.addSeparator()
        
        rules_filters_action = QAction(_("menus.rules_filters"), self)
        tools_menu.addAction(rules_filters_action)
        
        signatures_action = QAction(_("menus.signatures"), self)
        tools_menu.addAction(signatures_action)
        
        tools_menu.addSeparator()
        
        export_data_action = QAction(_("menus.export_data"), self)
        tools_menu.addAction(export_data_action)
        
        cleanup_tools_action = QAction(_("menus.cleanup_tools"), self)
        tools_menu.addAction(cleanup_tools_action)
        
        # Help Menu
        help_menu = menubar.addMenu(_("menus.help"))
        
        help_action = QAction("Help", self)
        help_action.setShortcut("F1")
        help_menu.addAction(help_action)
        
        keyboard_shortcuts_action = QAction("Keyboard Shortcuts", self)
        help_menu.addAction(keyboard_shortcuts_action)
        
        help_menu.addSeparator()
        
        check_updates_action = QAction(_("menus.check_updates"), self)
        help_menu.addAction(check_updates_action)
        
        help_menu.addSeparator()
        
        about_action = QAction(_("menus.about"), self)
        help_menu.addAction(about_action)
    
    def _setup_toolbars(self) -> None:
        """Set up the application toolbars."""
        # Main toolbar
        main_toolbar = self.addToolBar(_("toolbars.main"))
        main_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        
        # New Email button
        new_email_action = QAction(_("toolbars.new_email"), self)
        new_email_action.setShortcut("Ctrl+N")
        new_email_action.setToolTip(_("toolbars.new_email_tooltip"))
        main_toolbar.addAction(new_email_action)
        
        main_toolbar.addSeparator()
        
        # Reply buttons
        reply_action = QAction(_("toolbars.reply"), self)
        reply_action.setShortcut("Ctrl+R")
        main_toolbar.addAction(reply_action)
        
        reply_all_action = QAction(_("toolbars.reply_all"), self)
        reply_all_action.setShortcut("Ctrl+Shift+R")
        main_toolbar.addAction(reply_all_action)
        
        forward_action = QAction(_("toolbars.forward"), self)
        forward_action.setShortcut("Ctrl+F")
        main_toolbar.addAction(forward_action)
        
        main_toolbar.addSeparator()
        
        # Delete button
        delete_action = QAction(_("toolbars.delete"), self)
        delete_action.setShortcut("Delete")
        main_toolbar.addAction(delete_action)
    
    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        status_bar = self.statusBar()
        
        # Connection status
        self.connection_status = QLabel(_("main_window.status.not_connected"))
        status_bar.addWidget(self.connection_status)
        
        status_bar.addPermanentWidget(QLabel(_("main_window.status.app_version")))
    
    def _on_add_account(self) -> None:
        """Handle Add Account menu action."""
        if self.account_manager:
            try:
                account = self.account_manager.show_account_setup_wizard(self)
                if account:
                    self.connection_status.setText(_("main_window.status.account_added").format(name=account.name))
                    self.logger.info(f"Account added: {account.name} ({account.email_address})")
                    
                    # Refresh any UI components that show accounts
                    self._refresh_account_displays()
            except Exception as e:
                self.logger.error(f"Failed to add account: {e}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self,
                    _("main_window.dialogs.account_setup_error"),
                    _("main_window.dialogs.account_setup_failed").format(error=str(e))
                )
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                _("main_window.dialogs.feature_unavailable"),
                _("main_window.dialogs.account_management_unavailable")
            )
    
    def _on_account_manager(self) -> None:
        """Handle Account Manager menu action."""
        if self.account_manager:
            try:
                dialog = AccountManagerDialog(self.account_manager, self)
                dialog.accounts_changed.connect(self._on_accounts_changed)
                dialog.exec()
            except Exception as e:
                self.logger.error(f"Failed to show account manager: {e}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self,
                    _("main_window.dialogs.account_manager_error"),
                    _("main_window.dialogs.account_manager_failed").format(error=str(e))
                )
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                _("main_window.dialogs.feature_unavailable"),
                _("main_window.dialogs.account_management_unavailable")
            )
    
    def _on_account_settings(self) -> None:
        """Handle Account Settings menu action (legacy - redirects to Account Manager)."""
        self._on_account_manager()
    
    def _on_accounts_changed(self) -> None:
        """Handle when accounts have been modified in the Account Manager."""
        try:
            # Reload accounts
            self._load_accounts()
            
            # Re-setup email accounts
            self._setup_email_accounts()
            
            # Refresh account displays
            self._refresh_account_displays()
            
            self.logger.info("Account changes applied successfully")
            self.statusBar().showMessage(_("main_window.status.account_settings_updated"), 3000)
            
        except Exception as e:
            self.logger.error(f"Failed to apply account changes: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                _("main_window.dialogs.update_error"),
                _("main_window.dialogs.account_changes_failed").format(error=str(e))
            )
    
    def _refresh_account_displays(self) -> None:
        """Refresh account displays in the UI."""
        # This method can be extended later to update UI elements
        # that display account information
        pass 

    def _load_accounts(self):
        """Load saved email accounts."""
        try:
            accounts = self.account_manager.get_all_accounts()
            if accounts:
                self.logger.info(f"Loaded {len(accounts)} email accounts")
            else:
                self.logger.info("No email accounts configured")
        except Exception as e:
            self.logger.error(f"Failed to load accounts: {e}")
    
    def _setup_email_accounts(self):
        """Setup email accounts in the email manager."""
        try:
            accounts = self.account_manager.get_all_accounts()
            
            # Add accounts to email manager (this is quick, no network operations)
            for account in accounts:
                self.email_manager.add_account(account)
            
            # Load accounts in email view with cached data immediately
            if accounts and hasattr(self, 'email_widget'):
                # Load accounts in the background (this will handle connections asynchronously)
                self._setup_email_accounts_async(accounts, self.email_widget)
            
            self.logger.info("Email accounts setup completed")
            
        except Exception as e:
            self.logger.error(f"Failed to setup email accounts: {e}")
            self.statusBar().showMessage(_("main_window.status.email_setup_failed").format(error=str(e)), 5000)
    
    def _setup_email_accounts_async(self, accounts, email_widget):
        """Setup email account connections asynchronously."""
        from PyQt6.QtCore import QThread, QObject, pyqtSignal
        
        class EmailSetupWorker(QObject):
            finished = pyqtSignal()
            error = pyqtSignal(str)
            
            def __init__(self, email_manager, accounts):
                super().__init__()
                self.email_manager = email_manager
                self.accounts = accounts
            
            def run(self):
                try:
                    # Connect to accounts in background
                    self.email_manager.connect_all_accounts()
                    self.finished.emit()
                except Exception as e:
                    self.error.emit(str(e))
        
        # Create worker thread
        self.email_setup_thread = QThread()
        self.email_setup_worker = EmailSetupWorker(self.email_manager, accounts)
        self.email_setup_worker.moveToThread(self.email_setup_thread)
        
        # Connect signals
        self.email_setup_thread.started.connect(self.email_setup_worker.run)
        self.email_setup_worker.finished.connect(self._on_email_setup_finished)
        self.email_setup_worker.finished.connect(self.email_setup_thread.quit)
        self.email_setup_worker.error.connect(self._on_email_setup_error)
        self.email_setup_worker.error.connect(self.email_setup_thread.quit)
        
        # Start background setup
        self.connection_status.setText(_("main_window.status.connecting"))
        self.statusBar().showMessage(_("main_window.status.connecting_accounts"), 0)
        self.email_setup_thread.start()
        
        # Load accounts in EmailView (this should be quick without network operations)
        email_widget.load_accounts(accounts)
    
    def _on_email_setup_finished(self):
        """Called when email account setup completes."""
        self.statusBar().showMessage(_("main_window.status.email_connected"), 3000)
        self.connection_status.setText(_("main_window.status.connected"))
        if hasattr(self, 'email_widget'):
            # Refresh the email view now that connections are established
            # (accounts were already loaded in _setup_email_accounts_async)
            self.email_widget.refresh_folders_and_messages()
    
    def _on_email_setup_error(self, error_msg):
        """Called when email account setup fails."""
        self.logger.error(f"Email setup error: {error_msg}")
        self.connection_status.setText(_("main_window.status.connection_failed"))
        self.statusBar().showMessage(_("main_window.status.email_setup_failed").format(error=error_msg), 5000)

    def compose_new_email(self):
        """Create a new email."""
        accounts = self.account_manager.get_all_accounts()
        if not accounts:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, 
                _("main_window.dialogs.no_accounts_title"), 
                _("main_window.dialogs.no_accounts_message")
            )
            return
        
        composer = EmailComposer(self.email_manager, accounts, parent=self)
        composer.email_sent.connect(self.on_email_sent)
        composer.exec()
    
    def refresh_email(self):
        """Refresh email folders."""
        if hasattr(self, 'email_widget') and hasattr(self.email_widget, 'refresh_current_folder'):
            self.email_widget.refresh_current_folder()
        self.statusBar().showMessage(_("main_window.status.refreshing"), 2000)
    
    def on_email_sent(self, success: bool):
        """Handle email sent notification."""
        if success:
            self.statusBar().showMessage(_("main_window.status.email_sent"), 3000)
        else:
            self.statusBar().showMessage(_("main_window.status.email_send_failed"), 3000) 