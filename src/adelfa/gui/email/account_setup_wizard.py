"""
Account setup wizard for Adelfa PIM suite.

Provides a user-friendly wizard interface for setting up email accounts
with calendar and contact synchronization support.
"""

import re
import json
from typing import Optional, Dict, Any
from pathlib import Path
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QSpinBox,
    QGroupBox, QProgressBar, QTextEdit, QFormLayout, QFrame,
    QScrollArea, QWidget, QMessageBox, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QIcon

from ...utils.logging_setup import get_logger
from ...utils.i18n import get_translator
from ...core.email.protocol_detector import ProtocolDetector, DetectionResult, ServerSettings
from ...core.email.credential_manager import get_credential_manager, CredentialStorageError
from ...data.models.accounts import Account, SecurityType, EmailProtocol, AuthMethod, AccountType

logger = get_logger(__name__)
_ = get_translator()


class DetectionWorker(QThread):
    """Worker thread for protocol detection."""
    
    detection_completed = pyqtSignal(object)  # DetectionResult
    
    def __init__(self, email_address: str):
        super().__init__()
        self.email_address = email_address
        self.detector = ProtocolDetector()
    
    def run(self):
        """Run the detection process."""
        try:
            result = self.detector.detect_settings(self.email_address)
            self.detection_completed.emit(result)
        except Exception as e:
            logger.error(f"Detection worker failed: {e}")
            self.detection_completed.emit(DetectionResult(
                success=False,
                error_message=str(e)
            ))


class ConnectionTestWorker(QThread):
    """Worker thread for connection testing."""
    
    test_completed = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, settings: ServerSettings, username: str, password: str):
        super().__init__()
        self.settings = settings
        self.username = username
        self.password = password
        self.detector = ProtocolDetector()
    
    def run(self):
        """Run the connection test."""
        try:
            success, error = self.detector.test_connection(self.settings, self.username, self.password)
            message = _("account_setup.account_details.connection_success") if success else error
            self.test_completed.emit(success, message)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            self.test_completed.emit(False, str(e))


class AccountSetupWizard(QWizard):
    """
    Multi-step wizard for setting up email accounts with calendar and contacts.
    
    Provides a user-friendly interface for configuring email, calendar, and
    contact synchronization with automatic detection and connection testing.
    """
    
    # Page IDs
    PAGE_WELCOME = 0
    PAGE_PROVIDER = 1
    PAGE_ACCOUNT_DETAILS = 2
    PAGE_SERVER_SETTINGS = 3
    PAGE_CALENDAR_CONTACTS = 4
    PAGE_SUMMARY = 5
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = logger
        self.credential_manager = get_credential_manager()
        
        # Account data being configured
        self.account_data = {}
        self.detection_result: Optional[DetectionResult] = None
        
        self._setup_wizard()
        self._add_pages()
        
        # Start with welcome page
        self.setStartId(self.PAGE_WELCOME)
    
    def _setup_wizard(self):
        """Set up the wizard properties."""
        self.setWindowTitle(_("account_setup.title"))
        # Try to load icon from different possible locations
        import os
        icon_paths = []
        
        # Check if we're running in AppImage
        if os.getenv('APPDIR'):
            appdir = os.getenv('APPDIR')
            icon_paths.extend([
                f"{appdir}/adelfa.svg",
                f"{appdir}/usr/share/icons/hicolor/scalable/apps/adelfa.svg"
            ])
        
        # Development and fallback paths
        icon_paths.extend([
            ":/icons/adelfa.svg",  # Qt resource (if available)
            str(Path(__file__).parent.parent.parent / "resources" / "icons" / "adelfa.svg"),  # Development
            "./adelfa.svg",  # Current directory
        ])
        
        icon_loaded = False
        for icon_path in icon_paths:
            if os.path.exists(icon_path) or icon_path.startswith(":/"):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    icon_loaded = True
                    break
        
        if not icon_loaded:
            # Fallback to default system icon
            self.setWindowIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, True)
        self.setOption(QWizard.WizardOption.HelpButtonOnRight, False)
        
        # Set minimum size
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        
        # Connect help button
        self.helpRequested.connect(self._show_help)
    
    def _add_pages(self):
        """Add all wizard pages."""
        self.addPage(WelcomePage())
        self.addPage(ProviderSelectionPage())
        self.addPage(AccountDetailsPage())
        self.addPage(ServerSettingsPage())
        self.addPage(CalendarContactsPage())
        self.addPage(SummaryPage())
    
    def _show_help(self):
        """Show context-sensitive help."""
        current_page = self.currentPage()
        help_text = getattr(current_page, 'help_text', _("account_setup.help.general"))
        
        QMessageBox.information(
            self,
            _("account_setup.help.title"),
            help_text
        )


class WelcomePage(QWizardPage):
    """Welcome page introducing the account setup wizard."""
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the welcome page UI."""
        self.setTitle(_("account_setup.welcome.title"))
        self.setSubTitle(_("account_setup.welcome.subtitle"))
        
        layout = QVBoxLayout()
        
        # Add welcome content
        description = QLabel(_("account_setup.welcome.description"))
        description.setWordWrap(True)
        description.setStyleSheet("QLabel { font-size: 12pt; margin: 20px; }")
        layout.addWidget(description)
        
        # Add some spacing
        layout.addStretch()
        
        # Features list
        features_group = QGroupBox(_("account_setup.welcome.features"))
        features_layout = QVBoxLayout()
        
        features = [
            _("account_setup.welcome.feature_email"),
            _("account_setup.welcome.feature_calendar"),
            _("account_setup.welcome.feature_contacts"),
            _("account_setup.welcome.feature_security")
        ]
        
        for feature in features:
            label = QLabel(f"• {feature}")
            label.setStyleSheet("QLabel { font-size: 11pt; margin: 5px; }")
            features_layout.addWidget(label)
        
        features_group.setLayout(features_layout)
        layout.addWidget(features_group)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def nextId(self):
        """Return the next page ID."""
        return AccountSetupWizard.PAGE_PROVIDER


class ProviderSelectionPage(QWizardPage):
    """Page for selecting email provider or manual setup."""
    
    def __init__(self):
        super().__init__()
        self.detection_worker = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the provider selection page UI."""
        self.setTitle(_("account_setup.provider_selection.title"))
        self.setSubTitle(_("account_setup.provider_selection.subtitle"))
        
        layout = QVBoxLayout()
        
        # Setup type selection
        setup_group = QGroupBox(_("account_setup.provider_selection.setup_type"))
        setup_layout = QVBoxLayout()
        
        self.setup_button_group = QButtonGroup()
        
        self.auto_radio = QRadioButton(_("account_setup.provider_selection.automatic_setup"))
        self.auto_radio.setChecked(True)
        self.auto_radio.toggled.connect(self._on_setup_type_changed)
        self.setup_button_group.addButton(self.auto_radio)
        setup_layout.addWidget(self.auto_radio)
        
        self.manual_radio = QRadioButton(_("account_setup.provider_selection.manual_setup"))
        self.manual_radio.toggled.connect(self._on_setup_type_changed)
        self.setup_button_group.addButton(self.manual_radio)
        setup_layout.addWidget(self.manual_radio)
        
        setup_group.setLayout(setup_layout)
        layout.addWidget(setup_group)
        
        # Email address input (for automatic setup)
        self.auto_group = QGroupBox(_("account_setup.provider_selection.enter_email"))
        auto_layout = QFormLayout()
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText(_("account_setup.provider_selection.email_placeholder"))
        self.email_input.textChanged.connect(self._on_email_changed)
        auto_layout.addRow(_("account_setup.account_details.email_address"), self.email_input)
        
        # Detection button and progress
        detect_layout = QHBoxLayout()
        self.detect_button = QPushButton(_("account_setup.provider_selection.detect_settings"))
        self.detect_button.clicked.connect(self._detect_settings)
        self.detect_button.setEnabled(False)
        detect_layout.addWidget(self.detect_button)
        
        self.detection_progress = QProgressBar()
        self.detection_progress.setVisible(False)
        detect_layout.addWidget(self.detection_progress)
        
        auto_layout.addRow(detect_layout)
        
        # Detection status
        self.detection_status = QLabel()
        self.detection_status.setWordWrap(True)
        auto_layout.addRow(self.detection_status)
        
        self.auto_group.setLayout(auto_layout)
        layout.addWidget(self.auto_group)
        
        # Manual setup info
        self.manual_group = QGroupBox(_("account_setup.provider_selection.manual_setup"))
        manual_layout = QVBoxLayout()
        
        manual_info = QLabel(_("account_setup.provider_selection.manual_info"))
        manual_info.setWordWrap(True)
        manual_layout.addWidget(manual_info)
        
        self.manual_group.setLayout(manual_layout)
        self.manual_group.setVisible(False)
        layout.addWidget(self.manual_group)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Register fields
        self.registerField("email_address*", self.email_input)
        self.registerField("auto_setup", self.auto_radio)
    
    def _on_setup_type_changed(self):
        """Handle setup type selection change."""
        is_auto = self.auto_radio.isChecked()
        self.auto_group.setVisible(is_auto)
        self.manual_group.setVisible(not is_auto)
        
        if is_auto:
            self._on_email_changed()
        else:
            self.wizard().detection_result = None
    
    def _on_email_changed(self):
        """Handle email address input change."""
        email = self.email_input.text().strip()
        is_valid = self._is_valid_email(email)
        
        self.detect_button.setEnabled(is_valid)
        self.detection_status.clear()
        
        if is_valid:
            self.wizard().setField("email_address", email)
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _detect_settings(self):
        """Start automatic settings detection."""
        email = self.email_input.text().strip()
        
        self.detect_button.setEnabled(False)
        self.detection_progress.setVisible(True)
        self.detection_progress.setRange(0, 0)  # Indeterminate progress
        self.detection_status.setText(_("account_setup.provider_selection.detecting"))
        
        # Start detection in worker thread
        self.detection_worker = DetectionWorker(email)
        self.detection_worker.detection_completed.connect(self._on_detection_completed)
        self.detection_worker.start()
    
    def _on_detection_completed(self, result: DetectionResult):
        """Handle detection completion."""
        self.detection_progress.setVisible(False)
        self.detect_button.setEnabled(True)
        
        if result.success:
            self.detection_status.setText(_("account_setup.provider_selection.detection_success"))
            self.detection_status.setStyleSheet("color: green;")
            self.wizard().detection_result = result
        else:
            self.detection_status.setText(
                _("account_setup.provider_selection.detection_failed") + 
                (f" {result.error_message}" if result.error_message else "")
            )
            self.detection_status.setStyleSheet("color: red;")
            self.wizard().detection_result = None
        
        # Enable next button
        self.completeChanged.emit()
    
    def isComplete(self):
        """Check if the page is complete."""
        if self.manual_radio.isChecked():
            return True
        
        email = self.email_input.text().strip()
        return self._is_valid_email(email)
    
    def nextId(self):
        """Return the next page ID."""
        return AccountSetupWizard.PAGE_ACCOUNT_DETAILS


class AccountDetailsPage(QWizardPage):
    """Page for entering account details and credentials."""
    
    def __init__(self):
        super().__init__()
        self.connection_worker = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the account details page UI."""
        self.setTitle(_("account_setup.account_details.title"))
        self.setSubTitle(_("account_setup.account_details.subtitle"))
        
        layout = QVBoxLayout()
        
        # Account information
        account_group = QGroupBox(_("account_setup.summary.account_info"))
        form_layout = QFormLayout()
        
        self.account_name_input = QLineEdit()
        self.account_name_input.setPlaceholderText(_("account_setup.account_details.account_name_placeholder"))
        form_layout.addRow(_("account_setup.account_details.account_name"), self.account_name_input)
        
        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText(_("account_setup.account_details.display_name_placeholder"))
        form_layout.addRow(_("account_setup.account_details.display_name"), self.display_name_input)
        
        self.email_display = QLabel()
        self.email_display.setStyleSheet("font-weight: bold;")
        form_layout.addRow(_("account_setup.account_details.email_address"), self.email_display)
        
        account_group.setLayout(form_layout)
        layout.addWidget(account_group)
        
        # Credentials
        creds_group = QGroupBox(_("account_setup.account_details.credentials"))
        creds_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        creds_layout.addRow(_("account_setup.server_settings.username"), self.username_input)
        
        password_layout = QHBoxLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(_("account_setup.account_details.password_placeholder"))
        password_layout.addWidget(self.password_input)
        
        self.show_password_btn = QPushButton(_("account_setup.account_details.show_password"))
        self.show_password_btn.setCheckable(True)
        self.show_password_btn.toggled.connect(self._toggle_password_visibility)
        password_layout.addWidget(self.show_password_btn)
        
        creds_layout.addRow(_("account_setup.account_details.password"), password_layout)
        
        self.save_password_check = QCheckBox(_("account_setup.account_details.save_password"))
        self.save_password_check.setChecked(True)
        self.save_password_check.setToolTip(_("account_setup.account_details.save_password_help"))
        creds_layout.addRow(self.save_password_check)
        
        creds_group.setLayout(creds_layout)
        layout.addWidget(creds_group)
        
        # Connection test
        test_layout = QHBoxLayout()
        self.test_button = QPushButton(_("account_setup.account_details.test_connection"))
        self.test_button.clicked.connect(self._test_connection)
        test_layout.addWidget(self.test_button)
        
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        test_layout.addWidget(self.test_progress)
        
        test_layout.addStretch()
        layout.addLayout(test_layout)
        
        # Test status
        self.test_status = QLabel()
        self.test_status.setWordWrap(True)
        layout.addWidget(self.test_status)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Register fields
        self.registerField("account_name*", self.account_name_input)
        self.registerField("display_name", self.display_name_input)
        self.registerField("username*", self.username_input)
        self.registerField("password*", self.password_input)
        self.registerField("save_password", self.save_password_check)
    
    def initializePage(self):
        """Initialize the page with data from previous pages."""
        # Set email address from previous page
        email = self.wizard().field("email_address")
        self.email_display.setText(email)
        
        # Pre-fill username with email if not set
        if not self.username_input.text():
            self.username_input.setText(email)
        
        # Pre-fill account name if not set
        if not self.account_name_input.text():
            domain = email.split('@')[1] if '@' in email else ""
            if domain:
                account_name = f"{domain} {_('account_setup.account_details.default_account_name')}"
            else:
                account_name = _('account_setup.account_details.default_email_account')
            self.account_name_input.setText(account_name)
        
        # Check if we have detection results for automatic setup
        detection_result = getattr(self.wizard(), 'detection_result', None)
        if detection_result and detection_result.provider_name:
            provider_name = detection_result.provider_name
            account_name = f"{provider_name} {_('account_setup.account_details.default_account_name')}"
            self.account_name_input.setText(account_name)
    
    def _toggle_password_visibility(self, checked: bool):
        """Toggle password field visibility."""
        if checked:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_password_btn.setText(_("account_setup.account_details.hide_password"))
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_password_btn.setText(_("account_setup.account_details.show_password"))
    
    def _test_connection(self):
        """Test the connection with current settings."""
        # Get detection result for server settings
        detection_result = getattr(self.wizard(), 'detection_result', None)
        if not detection_result or not detection_result.email_settings:
            self.test_status.setText(_("account_setup.errors.no_server_settings"))
            self.test_status.setStyleSheet("color: red;")
            return
        
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            self.test_status.setText(_("account_setup.errors.empty_credentials"))
            self.test_status.setStyleSheet("color: red;")
            return
        
        # Use IMAP settings for testing
        imap_settings = detection_result.email_settings.get("imap")
        if not imap_settings:
            self.test_status.setText(_("account_setup.errors.no_imap_settings"))
            self.test_status.setStyleSheet("color: red;")
            return
        
        self.test_button.setEnabled(False)
        self.test_progress.setVisible(True)
        self.test_progress.setRange(0, 0)
        self.test_status.setText(_("account_setup.account_details.testing"))
        self.test_status.setStyleSheet("")
        
        # Start connection test in worker thread
        self.connection_worker = ConnectionTestWorker(imap_settings, username, password)
        self.connection_worker.test_completed.connect(self._on_test_completed)
        self.connection_worker.start()
    
    def _on_test_completed(self, success: bool, message: str):
        """Handle connection test completion."""
        self.test_progress.setVisible(False)
        self.test_button.setEnabled(True)
        
        self.test_status.setText(message)
        if success:
            self.test_status.setStyleSheet("color: green;")
        else:
            self.test_status.setStyleSheet("color: red;")
    
    def nextId(self):
        """Return the next page ID."""
        # Skip server settings if we have auto-detection results
        detection_result = getattr(self.wizard(), 'detection_result', None)
        if detection_result and detection_result.email_settings:
            return AccountSetupWizard.PAGE_CALENDAR_CONTACTS
        else:
            return AccountSetupWizard.PAGE_SERVER_SETTINGS


class ServerSettingsPage(QWizardPage):
    """Page for manual server configuration."""
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the server settings page UI."""
        self.setTitle(_("account_setup.server_settings.title"))
        self.setSubTitle(_("account_setup.server_settings.subtitle"))
        
        layout = QVBoxLayout()
        
        # Incoming mail settings
        incoming_group = QGroupBox(_("account_setup.server_settings.incoming_mail"))
        incoming_layout = QFormLayout()
        
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems([
            _("account_setup.server_settings.protocol_options.imap"),
            _("account_setup.server_settings.protocol_options.pop3")
        ])
        incoming_layout.addRow(_("account_setup.server_settings.protocol"), self.protocol_combo)
        
        self.incoming_server_input = QLineEdit()
        incoming_layout.addRow(_("account_setup.server_settings.server"), self.incoming_server_input)
        
        self.incoming_port_input = QSpinBox()
        self.incoming_port_input.setRange(1, 65535)
        self.incoming_port_input.setValue(993)
        incoming_layout.addRow(_("account_setup.server_settings.port"), self.incoming_port_input)
        
        self.incoming_security_combo = QComboBox()
        for security in SecurityType:
            self.incoming_security_combo.addItem(
                _(f"account_setup.server_settings.security_options.{security.value}"),
                security
            )
        incoming_layout.addRow(_("account_setup.server_settings.security"), self.incoming_security_combo)
        
        incoming_group.setLayout(incoming_layout)
        layout.addWidget(incoming_group)
        
        # Outgoing mail settings
        outgoing_group = QGroupBox(_("account_setup.server_settings.outgoing_mail"))
        outgoing_layout = QFormLayout()
        
        self.outgoing_server_input = QLineEdit()
        outgoing_layout.addRow(_("account_setup.server_settings.server"), self.outgoing_server_input)
        
        self.outgoing_port_input = QSpinBox()
        self.outgoing_port_input.setRange(1, 65535)
        self.outgoing_port_input.setValue(587)
        outgoing_layout.addRow(_("account_setup.server_settings.port"), self.outgoing_port_input)
        
        self.outgoing_security_combo = QComboBox()
        for security in SecurityType:
            self.outgoing_security_combo.addItem(
                _(f"account_setup.server_settings.security_options.{security.value}"),
                security
            )
        outgoing_layout.addRow(_("account_setup.server_settings.security"), self.outgoing_security_combo)
        
        self.auth_required_check = QCheckBox(_("account_setup.server_settings.auth_required"))
        self.auth_required_check.setChecked(True)
        outgoing_layout.addRow(self.auth_required_check)
        
        outgoing_group.setLayout(outgoing_layout)
        layout.addWidget(outgoing_group)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Register fields
        self.registerField("incoming_server*", self.incoming_server_input)
        self.registerField("incoming_port", self.incoming_port_input)
        self.registerField("outgoing_server*", self.outgoing_server_input)
        self.registerField("outgoing_port", self.outgoing_port_input)
    
    def nextId(self):
        """Return the next page ID."""
        return AccountSetupWizard.PAGE_CALENDAR_CONTACTS


class CalendarContactsPage(QWizardPage):
    """Page for configuring calendar and contact synchronization."""
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the calendar and contacts page UI."""
        self.setTitle(_("account_setup.calendar_contacts.title"))
        self.setSubTitle(_("account_setup.calendar_contacts.subtitle"))
        
        layout = QVBoxLayout()
        
        # Calendar settings
        calendar_group = QGroupBox(_("account_setup.calendar_contacts.enable_calendar"))
        calendar_layout = QFormLayout()
        
        self.enable_calendar_check = QCheckBox(_("account_setup.calendar_contacts.enable_calendar"))
        self.enable_calendar_check.toggled.connect(self._on_calendar_toggled)
        calendar_layout.addRow(self.enable_calendar_check)
        
        self.calendar_server_input = QLineEdit()
        self.calendar_server_input.setPlaceholderText(_("account_setup.calendar_contacts.server_url_placeholder"))
        self.calendar_server_input.setEnabled(False)
        calendar_layout.addRow(_("account_setup.calendar_contacts.server_url"), self.calendar_server_input)
        
        self.calendar_username_input = QLineEdit()
        self.calendar_username_input.setEnabled(False)
        calendar_layout.addRow(_("account_setup.calendar_contacts.username"), self.calendar_username_input)
        
        self.calendar_password_input = QLineEdit()
        self.calendar_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.calendar_password_input.setEnabled(False)
        calendar_layout.addRow(_("account_setup.calendar_contacts.password"), self.calendar_password_input)
        
        calendar_group.setLayout(calendar_layout)
        layout.addWidget(calendar_group)
        
        # Contacts settings
        contacts_group = QGroupBox(_("account_setup.calendar_contacts.enable_contacts"))
        contacts_layout = QFormLayout()
        
        self.enable_contacts_check = QCheckBox(_("account_setup.calendar_contacts.enable_contacts"))
        self.enable_contacts_check.toggled.connect(self._on_contacts_toggled)
        contacts_layout.addRow(self.enable_contacts_check)
        
        self.contacts_server_input = QLineEdit()
        self.contacts_server_input.setPlaceholderText(_("account_setup.calendar_contacts.server_url_placeholder"))
        self.contacts_server_input.setEnabled(False)
        contacts_layout.addRow(_("account_setup.calendar_contacts.server_url"), self.contacts_server_input)
        
        self.contacts_username_input = QLineEdit()
        self.contacts_username_input.setEnabled(False)
        contacts_layout.addRow(_("account_setup.calendar_contacts.username"), self.contacts_username_input)
        
        self.contacts_password_input = QLineEdit()
        self.contacts_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.contacts_password_input.setEnabled(False)
        contacts_layout.addRow(_("account_setup.calendar_contacts.password"), self.contacts_password_input)
        
        contacts_group.setLayout(contacts_layout)
        layout.addWidget(contacts_group)
        
        # Sync settings
        sync_group = QGroupBox(_("account_setup.calendar_contacts.sync_frequency"))
        sync_layout = QFormLayout()
        
        self.sync_frequency_combo = QComboBox()
        sync_options = [
            ("manual", _("account_setup.calendar_contacts.sync_options.manual")),
            ("5min", _("account_setup.calendar_contacts.sync_options.5min")),
            ("15min", _("account_setup.calendar_contacts.sync_options.15min")),
            ("30min", _("account_setup.calendar_contacts.sync_options.30min")),
            ("1hour", _("account_setup.calendar_contacts.sync_options.1hour")),
            ("daily", _("account_setup.calendar_contacts.sync_options.daily"))
        ]
        
        for value, text in sync_options:
            self.sync_frequency_combo.addItem(text, value)
        
        self.sync_frequency_combo.setCurrentIndex(2)  # Default to 15min
        sync_layout.addRow(_("account_setup.calendar_contacts.sync_frequency"), self.sync_frequency_combo)
        
        sync_group.setLayout(sync_layout)
        layout.addWidget(sync_group)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Register fields
        self.registerField("enable_calendar", self.enable_calendar_check)
        self.registerField("calendar_server", self.calendar_server_input)
        self.registerField("enable_contacts", self.enable_contacts_check)
        self.registerField("contacts_server", self.contacts_server_input)
    
    def initializePage(self):
        """Initialize the page with auto-detected settings if available."""
        detection_result = getattr(self.wizard(), 'detection_result', None)
        if detection_result:
            # Auto-fill CalDAV settings
            if detection_result.caldav_url:
                self.enable_calendar_check.setChecked(True)
                self.calendar_server_input.setText(detection_result.caldav_url)
                
                # Use same credentials as email
                email = self.wizard().field("email_address")
                username = self.wizard().field("username")
                if username:
                    self.calendar_username_input.setText(username)
                elif email:
                    self.calendar_username_input.setText(email)
            
            # Auto-fill CardDAV settings
            if detection_result.carddav_url:
                self.enable_contacts_check.setChecked(True)
                self.contacts_server_input.setText(detection_result.carddav_url)
                
                # Use same credentials as email
                email = self.wizard().field("email_address")
                username = self.wizard().field("username")
                if username:
                    self.contacts_username_input.setText(username)
                elif email:
                    self.contacts_username_input.setText(email)
    
    def _on_calendar_toggled(self, checked: bool):
        """Handle calendar checkbox toggle."""
        self.calendar_server_input.setEnabled(checked)
        self.calendar_username_input.setEnabled(checked)
        self.calendar_password_input.setEnabled(checked)
    
    def _on_contacts_toggled(self, checked: bool):
        """Handle contacts checkbox toggle."""
        self.contacts_server_input.setEnabled(checked)
        self.contacts_username_input.setEnabled(checked)
        self.contacts_password_input.setEnabled(checked)
    
    def nextId(self):
        """Return the next page ID."""
        return AccountSetupWizard.PAGE_SUMMARY


class SummaryPage(QWizardPage):
    """Final page showing configuration summary."""
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the summary page UI."""
        self.setTitle(_("account_setup.summary.title"))
        self.setSubTitle(_("account_setup.summary.subtitle"))
        
        # Create scroll area for the summary
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.summary_widget = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_widget)
        
        scroll.setWidget(self.summary_widget)
        
        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.setLayout(layout)
    
    def initializePage(self):
        """Initialize the summary page with collected data."""
        # Clear previous content
        for i in reversed(range(self.summary_layout.count())):
            self.summary_layout.itemAt(i).widget().setParent(None)
        
        # Account information
        account_group = QGroupBox(_("account_setup.summary.account_info"))
        account_layout = QFormLayout()
        
        account_layout.addRow(_("account_setup.account_details.account_name"), 
                            QLabel(self.wizard().field("account_name")))
        account_layout.addRow(_("account_setup.account_details.display_name"), 
                            QLabel(self.wizard().field("display_name") or _("account_setup.summary.not_set")))
        account_layout.addRow(_("account_setup.account_details.email_address"), 
                            QLabel(self.wizard().field("email_address")))
        
        account_group.setLayout(account_layout)
        self.summary_layout.addWidget(account_group)
        
        # Email settings
        email_group = QGroupBox(_("account_setup.summary.email_settings"))
        email_layout = QFormLayout()
        
        detection_result = getattr(self.wizard(), 'detection_result', None)
        if detection_result and detection_result.email_settings:
            # Show auto-detected settings
            imap_settings = detection_result.email_settings.get("imap")
            smtp_settings = detection_result.email_settings.get("smtp")
            
            if imap_settings:
                email_layout.addRow(_("account_setup.server_settings.incoming_mail"), 
                                  QLabel(f"{imap_settings.server}:{imap_settings.port} ({imap_settings.security.value})"))
            
            if smtp_settings:
                email_layout.addRow(_("account_setup.server_settings.outgoing_mail"), 
                                  QLabel(f"{smtp_settings.server}:{smtp_settings.port} ({smtp_settings.security.value})"))
        else:
            # Show manual settings
            incoming_server = self.wizard().field("incoming_server")
            incoming_port = self.wizard().field("incoming_port")
            outgoing_server = self.wizard().field("outgoing_server")
            outgoing_port = self.wizard().field("outgoing_port")
            
            email_layout.addRow(_("account_setup.server_settings.incoming_mail"), 
                              QLabel(f"{incoming_server}:{incoming_port}"))
            email_layout.addRow(_("account_setup.server_settings.outgoing_mail"), 
                              QLabel(f"{outgoing_server}:{outgoing_port}"))
        
        email_group.setLayout(email_layout)
        self.summary_layout.addWidget(email_group)
        
        # Calendar settings
        calendar_group = QGroupBox(_("account_setup.summary.calendar_settings"))
        calendar_layout = QFormLayout()
        
        if self.wizard().field("enable_calendar"):
            calendar_layout.addRow(_("account_setup.summary.enabled"), QLabel("✓"))
            calendar_server = self.wizard().field("calendar_server")
            if calendar_server:
                calendar_layout.addRow(_("account_setup.calendar_contacts.server_url"), QLabel(calendar_server))
        else:
            calendar_layout.addRow(_("account_setup.summary.disabled"), QLabel("✗"))
        
        calendar_group.setLayout(calendar_layout)
        self.summary_layout.addWidget(calendar_group)
        
        # Contacts settings
        contacts_group = QGroupBox(_("account_setup.summary.contacts_settings"))
        contacts_layout = QFormLayout()
        
        if self.wizard().field("enable_contacts"):
            contacts_layout.addRow(_("account_setup.summary.enabled"), QLabel("✓"))
            contacts_server = self.wizard().field("contacts_server")
            if contacts_server:
                contacts_layout.addRow(_("account_setup.calendar_contacts.server_url"), QLabel(contacts_server))
        else:
            contacts_layout.addRow(_("account_setup.summary.disabled"), QLabel("✗"))
        
        contacts_group.setLayout(contacts_layout)
        self.summary_layout.addWidget(contacts_group)
        
        self.summary_layout.addStretch()
    
    def nextId(self):
        """This is the final page."""
        return -1 