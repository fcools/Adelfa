"""
Account Manager Dialog for Adelfa PIM suite.

Provides a comprehensive interface for managing email accounts including
viewing, editing, testing connections, and managing credentials.
"""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QGroupBox, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QCheckBox, QLabel, QTextEdit, QTabWidget, QWidget, QMessageBox,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QIcon, QFont

from ...data.models.accounts import Account, SecurityType, EmailProtocol, AuthMethod
from ...core.email.account_manager import AccountManager
from ...core.email.credential_manager import get_credential_manager
from ...utils.logging_setup import get_logger

logger = get_logger(__name__)


class ConnectionTestWorker(QThread):
    """Worker thread for testing account connections."""
    
    test_completed = pyqtSignal(str, bool, str)  # test_type, success, message
    
    def __init__(self, account_manager: AccountManager, account: Account):
        super().__init__()
        self.account_manager = account_manager
        self.account = account
        
    def run(self):
        """Run connection tests."""
        try:
            # Test incoming connection
            success, error = self.account_manager._test_incoming_connection(self.account)
            if success:
                self.test_completed.emit("incoming", True, "IMAP connection successful")
            else:
                self.test_completed.emit("incoming", False, f"IMAP failed: {error}")
            
            # Test outgoing connection
            success, error = self.account_manager._test_outgoing_connection(self.account)
            if success:
                self.test_completed.emit("outgoing", True, "SMTP connection successful")
            else:
                self.test_completed.emit("outgoing", False, f"SMTP failed: {error}")
                
        except Exception as e:
            self.test_completed.emit("error", False, f"Test error: {e}")


class AccountEditDialog(QDialog):
    """Dialog for editing account settings."""
    
    account_updated = pyqtSignal(Account)
    
    def __init__(self, account: Account, account_manager: AccountManager, parent=None):
        super().__init__(parent)
        self.account = account
        self.account_manager = account_manager
        self.credential_manager = get_credential_manager()
        self.test_worker = None
        
        self.setWindowTitle(f"Edit Account - {account.name}")
        self.setModal(True)
        self.resize(600, 500)
        
        self.setup_ui()
        self.load_account_data()
        
    def setup_ui(self):
        """Setup the account edit dialog UI."""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Account info tab
        self.setup_account_info_tab()
        
        # Email settings tab
        self.setup_email_settings_tab()
        
        # Connection test tab
        self.setup_connection_test_tab()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        button_layout.addWidget(self.test_btn)
        
        button_layout.addStretch()
        
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_account)
        button_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def setup_account_info_tab(self):
        """Setup account information tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Basic info group
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)
        
        self.name_edit = QLineEdit()
        basic_layout.addRow("Account Name:", self.name_edit)
        
        self.email_edit = QLineEdit()
        basic_layout.addRow("Email Address:", self.email_edit)
        
        self.display_name_edit = QLineEdit()
        basic_layout.addRow("Display Name:", self.display_name_edit)
        
        self.enabled_check = QCheckBox("Account Enabled")
        basic_layout.addRow("", self.enabled_check)
        
        self.default_check = QCheckBox("Default Account")
        basic_layout.addRow("", self.default_check)
        
        layout.addWidget(basic_group)
        
        # Status group
        status_group = QGroupBox("Account Status")
        status_layout = QFormLayout(status_group)
        
        self.status_label = QLabel()
        status_layout.addRow("Connection Status:", self.status_label)
        
        self.last_sync_label = QLabel()
        status_layout.addRow("Last Sync:", self.last_sync_label)
        
        self.last_error_edit = QTextEdit()
        self.last_error_edit.setMaximumHeight(60)
        self.last_error_edit.setReadOnly(True)
        status_layout.addRow("Last Error:", self.last_error_edit)
        
        layout.addWidget(status_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Account Info")
        
    def setup_email_settings_tab(self):
        """Setup email settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Incoming mail group
        incoming_group = QGroupBox("Incoming Mail (IMAP)")
        incoming_layout = QFormLayout(incoming_group)
        
        self.imap_server_edit = QLineEdit()
        incoming_layout.addRow("Server:", self.imap_server_edit)
        
        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(993)
        incoming_layout.addRow("Port:", self.imap_port_spin)
        
        self.imap_security_combo = QComboBox()
        self.imap_security_combo.addItems(["TLS/SSL", "STARTTLS", "None"])
        incoming_layout.addRow("Security:", self.imap_security_combo)
        
        self.imap_username_edit = QLineEdit()
        incoming_layout.addRow("Username:", self.imap_username_edit)
        
        self.imap_password_edit = QLineEdit()
        self.imap_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        incoming_layout.addRow("Password:", self.imap_password_edit)
        
        layout.addWidget(incoming_group)
        
        # Outgoing mail group
        outgoing_group = QGroupBox("Outgoing Mail (SMTP)")
        outgoing_layout = QFormLayout(outgoing_group)
        
        self.smtp_server_edit = QLineEdit()
        outgoing_layout.addRow("Server:", self.smtp_server_edit)
        
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(587)
        outgoing_layout.addRow("Port:", self.smtp_port_spin)
        
        self.smtp_security_combo = QComboBox()
        self.smtp_security_combo.addItems(["STARTTLS", "TLS/SSL", "None"])
        outgoing_layout.addRow("Security:", self.smtp_security_combo)
        
        self.smtp_username_edit = QLineEdit()
        outgoing_layout.addRow("Username:", self.smtp_username_edit)
        
        self.smtp_password_edit = QLineEdit()
        self.smtp_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        outgoing_layout.addRow("Password:", self.smtp_password_edit)
        
        self.smtp_auth_check = QCheckBox("Authentication Required")
        self.smtp_auth_check.setChecked(True)
        outgoing_layout.addRow("", self.smtp_auth_check)
        
        layout.addWidget(outgoing_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Email Settings")
        
    def setup_connection_test_tab(self):
        """Setup connection test tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Test controls
        test_group = QGroupBox("Connection Testing")
        test_layout = QVBoxLayout(test_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        test_layout.addWidget(self.progress_bar)
        
        # Test results
        self.test_results = QTextEdit()
        self.test_results.setReadOnly(True)
        test_layout.addWidget(self.test_results)
        
        layout.addWidget(test_group)
        
        # Test history
        history_group = QGroupBox("Test History")
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Time", "Type", "Result", "Error"])
        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(True)
        history_layout.addWidget(self.history_table)
        
        layout.addWidget(history_group)
        
        self.tab_widget.addTab(tab, "Connection Test")
        
    def load_account_data(self):
        """Load account data into the form."""
        # Basic info
        self.name_edit.setText(self.account.name or "")
        self.email_edit.setText(self.account.email_address or "")
        self.display_name_edit.setText(self.account.display_name or "")
        self.enabled_check.setChecked(self.account.is_enabled)
        self.default_check.setChecked(self.account.is_default)
        
        # Status
        self.status_label.setText(self.account.connection_status or "Unknown")
        if self.account.last_sync:
            self.last_sync_label.setText(self.account.last_sync.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self.last_sync_label.setText("Never")
        
        self.last_error_edit.setPlainText(self.account.last_error or "")
        
        # Email settings
        self.imap_server_edit.setText(self.account.incoming_server or "")
        self.imap_port_spin.setValue(self.account.incoming_port or 993)
        
        # Security mapping
        security_map = {
            SecurityType.TLS_SSL: "TLS/SSL",
            SecurityType.STARTTLS: "STARTTLS", 
            SecurityType.NONE: "None"
        }
        
        imap_security = security_map.get(self.account.incoming_security, "TLS/SSL")
        self.imap_security_combo.setCurrentText(imap_security)
        
        self.imap_username_edit.setText(self.account.incoming_username or "")
        
        self.smtp_server_edit.setText(self.account.outgoing_server or "")
        self.smtp_port_spin.setValue(self.account.outgoing_port or 587)
        
        smtp_security = security_map.get(self.account.outgoing_security, "STARTTLS")
        self.smtp_security_combo.setCurrentText(smtp_security)
        
        self.smtp_username_edit.setText(self.account.outgoing_username or "")
        self.smtp_auth_check.setChecked(self.account.outgoing_auth_required)
        
        # Load stored passwords
        self.load_stored_passwords()
        
        # Load test history
        self.load_test_history()
        
    def load_stored_passwords(self):
        """Load stored passwords from credential manager."""
        try:
            if self.account.incoming_password_key:
                password = self.credential_manager.retrieve_password(self.account.incoming_password_key)
                if password:
                    self.imap_password_edit.setText(password)
                    
            if self.account.outgoing_password_key:
                password = self.credential_manager.retrieve_password(self.account.outgoing_password_key)
                if password:
                    self.smtp_password_edit.setText(password)
                    
        except Exception as e:
            logger.warning(f"Failed to load stored passwords: {e}")
            
    def load_test_history(self):
        """Load connection test history."""
        try:
            history = self.account_manager.repository.get_connection_test_history(self.account.id)
            
            self.history_table.setRowCount(len(history))
            for row, test in enumerate(history):
                self.history_table.setItem(row, 0, QTableWidgetItem(
                    test.tested_at.strftime("%Y-%m-%d %H:%M:%S")
                ))
                self.history_table.setItem(row, 1, QTableWidgetItem(test.test_type))
                self.history_table.setItem(row, 2, QTableWidgetItem(test.test_result))
                self.history_table.setItem(row, 3, QTableWidgetItem(test.error_message or ""))
                
        except Exception as e:
            logger.warning(f"Failed to load test history: {e}")
            
    def test_connection(self):
        """Test account connections."""
        if self.test_worker and self.test_worker.isRunning():
            return
            
        # Update account with current form data before testing
        self.update_account_from_form()
        
        self.test_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        self.test_results.clear()
        self.test_results.append("Starting connection tests...\n")
        
        self.test_worker = ConnectionTestWorker(self.account_manager, self.account)
        self.test_worker.test_completed.connect(self.on_test_completed)
        self.test_worker.finished.connect(self.on_testing_finished)
        self.test_worker.start()
        
    @pyqtSlot(str, bool, str)
    def on_test_completed(self, test_type: str, success: bool, message: str):
        """Handle test completion."""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        self.test_results.append(f"{test_type.upper()}: {status} - {message}")
        
    def on_testing_finished(self):
        """Handle testing finished."""
        self.test_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.test_results.append("\nTesting completed.")
        
        # Reload test history
        self.load_test_history()
        
    def update_account_from_form(self):
        """Update account object from form data."""
        self.account.name = self.name_edit.text()
        self.account.email_address = self.email_edit.text()
        self.account.display_name = self.display_name_edit.text()
        self.account.is_enabled = self.enabled_check.isChecked()
        
        # Email settings
        self.account.incoming_server = self.imap_server_edit.text()
        self.account.incoming_port = self.imap_port_spin.value()
        self.account.incoming_username = self.imap_username_edit.text()
        
        self.account.outgoing_server = self.smtp_server_edit.text()
        self.account.outgoing_port = self.smtp_port_spin.value()
        self.account.outgoing_username = self.smtp_username_edit.text()
        self.account.outgoing_auth_required = self.smtp_auth_check.isChecked()
        
        # Security types
        security_map = {
            "TLS/SSL": SecurityType.TLS_SSL,
            "STARTTLS": SecurityType.STARTTLS,
            "None": SecurityType.NONE
        }
        
        self.account.incoming_security = security_map[self.imap_security_combo.currentText()]
        self.account.outgoing_security = security_map[self.smtp_security_combo.currentText()]
        
    def save_account(self):
        """Save account changes."""
        try:
            self.update_account_from_form()
            
            # Prepare update data
            updates = {
                'name': self.account.name,
                'email_address': self.account.email_address,
                'display_name': self.account.display_name,
                'is_enabled': self.account.is_enabled,
                'incoming_server': self.account.incoming_server,
                'incoming_port': self.account.incoming_port,
                'incoming_username': self.account.incoming_username,
                'outgoing_server': self.account.outgoing_server,
                'outgoing_port': self.account.outgoing_port,
                'outgoing_username': self.account.outgoing_username,
                'outgoing_auth_required': self.account.outgoing_auth_required,
                'incoming_security': self.account.incoming_security,
                'outgoing_security': self.account.outgoing_security
            }
            
            # Update passwords if changed
            imap_password = self.imap_password_edit.text()
            if imap_password:
                updates['incoming_password'] = imap_password
                
            smtp_password = self.smtp_password_edit.text()
            if smtp_password:
                updates['outgoing_password'] = smtp_password
            
            # Handle default account
            if self.default_check.isChecked():
                self.account_manager.repository.set_default_account(self.account.id)
            
            # Update account
            success = self.account_manager.repository.update_account(self.account.id, updates)
            
            if success:
                QMessageBox.information(self, _("email.account_manager.groups.settings_saved"),
                                        _("email.account_manager.messages.account_updated"))
                self.accept()
            except Exception as e:
                # Failed to save to database
                QMessageBox.warning(self, _("email.account_manager.messages.save_error"), _("email.account_manager.messages.save_db_failed"))
            except AttributeError:
                QMessageBox.critical(self, _("email.account_manager.messages.save_error"), _("email.account_manager.messages.no_account_manager"))
            except Exception as e:
                QMessageBox.critical(self, _("email.account_manager.messages.save_error"), _("email.account_manager.messages.save_settings_failed").format(error=str(e)))


class QuickServerConfigDialog(QDialog):
    """Quick dialog for configuring server settings."""
    
    def __init__(self, account: Account, parent=None):
        super().__init__(parent)
        self.account = account
        
        self.setWindowTitle(f"Server Configuration - {account.name}")
        self.setModal(True)
        self.resize(500, 400)
        
        self.setup_ui()
        self.load_current_settings()
        
    def setup_ui(self):
        """Setup the server configuration UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel(f"Configure email servers for: {self.account.email_address}")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(header_label)
        
        # IMAP Server Group
        imap_group = QGroupBox("Incoming Mail Server (IMAP)")
        imap_layout = QFormLayout(imap_group)
        
        self.imap_server_edit = QLineEdit()
        self.imap_server_edit.setPlaceholderText("e.g., imap.gmail.com")
        imap_layout.addRow("IMAP Server:", self.imap_server_edit)
        
        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(993)
        imap_layout.addRow("Port:", self.imap_port_spin)
        
        self.imap_security_combo = QComboBox()
        self.imap_security_combo.addItems(["TLS/SSL (993)", "STARTTLS (143)", "None (143)"])
        imap_layout.addRow("Security:", self.imap_security_combo)
        
        self.imap_username_edit = QLineEdit()
        imap_layout.addRow("Username:", self.imap_username_edit)
        
        self.imap_password_edit = QLineEdit()
        self.imap_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        imap_layout.addRow("Password:", self.imap_password_edit)
        
        layout.addWidget(imap_group)
        
        # SMTP Server Group
        smtp_group = QGroupBox("Outgoing Mail Server (SMTP)")
        smtp_layout = QFormLayout(smtp_group)
        
        self.smtp_server_edit = QLineEdit()
        self.smtp_server_edit.setPlaceholderText("e.g., smtp.gmail.com")
        smtp_layout.addRow("SMTP Server:", self.smtp_server_edit)
        
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(587)
        smtp_layout.addRow("Port:", self.smtp_port_spin)
        
        self.smtp_security_combo = QComboBox()
        self.smtp_security_combo.addItems(["STARTTLS (587)", "TLS/SSL (465)", "None (25)"])
        smtp_layout.addRow("Security:", self.smtp_security_combo)
        
        self.smtp_username_edit = QLineEdit()
        smtp_layout.addRow("Username:", self.smtp_username_edit)
        
        self.smtp_password_edit = QLineEdit()
        self.smtp_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        smtp_layout.addRow("Password:", self.smtp_password_edit)
        
        layout.addWidget(smtp_group)
        
        # Common provider buttons
        provider_group = QGroupBox("Quick Setup for Common Providers")
        provider_layout = QHBoxLayout(provider_group)
        
        gmail_btn = QPushButton("Gmail")
        gmail_btn.clicked.connect(self.setup_gmail)
        provider_layout.addWidget(gmail_btn)
        
        outlook_btn = QPushButton("Outlook/Hotmail")
        outlook_btn.clicked.connect(self.setup_outlook)
        provider_layout.addWidget(outlook_btn)
        
        yahoo_btn = QPushButton("Yahoo")
        yahoo_btn.clicked.connect(self.setup_yahoo)
        provider_layout.addWidget(yahoo_btn)
        
        layout.addWidget(provider_group)
        
        # Test and Save buttons
        button_layout = QHBoxLayout()
        
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self.test_connection)
        button_layout.addWidget(test_btn)
        
        button_layout.addStretch()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
    def load_current_settings(self):
        """Load current account settings into the form."""
        # IMAP settings
        self.imap_server_edit.setText(self.account.incoming_server or "")
        self.imap_port_spin.setValue(self.account.incoming_port or 993)
        self.imap_username_edit.setText(self.account.incoming_username or "")
        
        # SMTP settings  
        self.smtp_server_edit.setText(self.account.outgoing_server or "")
        self.smtp_port_spin.setValue(self.account.outgoing_port or 587)
        self.smtp_username_edit.setText(self.account.outgoing_username or "")
        
        # Load stored passwords
        credential_manager = get_credential_manager()
        
        if self.account.incoming_password_key:
            try:
                password = credential_manager.retrieve_password(self.account.incoming_password_key)
                if password:
                    self.imap_password_edit.setText(password)
            except:
                pass
                
        if self.account.outgoing_password_key:
            try:
                password = credential_manager.retrieve_password(self.account.outgoing_password_key)
                if password:
                    self.smtp_password_edit.setText(password)
            except:
                pass
        
        # Set security combo based on current settings
        if self.account.incoming_security:
            security_map = {
                "TLS_SSL": "TLS/SSL (993)",
                "STARTTLS": "STARTTLS (143)", 
                "NONE": "None (143)"
            }
            security_text = security_map.get(self.account.incoming_security.name, "TLS/SSL (993)")
            self.imap_security_combo.setCurrentText(security_text)
            
        if self.account.outgoing_security:
            security_map = {
                "STARTTLS": "STARTTLS (587)",
                "TLS_SSL": "TLS/SSL (465)",
                "NONE": "None (25)"
            }
            security_text = security_map.get(self.account.outgoing_security.name, "STARTTLS (587)")
            self.smtp_security_combo.setCurrentText(security_text)
            
    def setup_gmail(self):
        """Quick setup for Gmail."""
        self.imap_server_edit.setText("imap.gmail.com")
        self.imap_port_spin.setValue(993)
        self.imap_security_combo.setCurrentText("TLS/SSL (993)")
        
        self.smtp_server_edit.setText("smtp.gmail.com")
        self.smtp_port_spin.setValue(587)
        self.smtp_security_combo.setCurrentText("STARTTLS (587)")
        
        # Auto-fill usernames if not set
        if not self.imap_username_edit.text():
            self.imap_username_edit.setText(self.account.email_address)
        if not self.smtp_username_edit.text():
            self.smtp_username_edit.setText(self.account.email_address)
            
    def setup_outlook(self):
        """Quick setup for Outlook/Hotmail."""
        self.imap_server_edit.setText("outlook.office365.com")
        self.imap_port_spin.setValue(993)
        self.imap_security_combo.setCurrentText("TLS/SSL (993)")
        
        self.smtp_server_edit.setText("smtp-mail.outlook.com")
        self.smtp_port_spin.setValue(587)
        self.smtp_security_combo.setCurrentText("STARTTLS (587)")
        
        if not self.imap_username_edit.text():
            self.imap_username_edit.setText(self.account.email_address)
        if not self.smtp_username_edit.text():
            self.smtp_username_edit.setText(self.account.email_address)
            
    def setup_yahoo(self):
        """Quick setup for Yahoo."""
        self.imap_server_edit.setText("imap.mail.yahoo.com")
        self.imap_port_spin.setValue(993)
        self.imap_security_combo.setCurrentText("TLS/SSL (993)")
        
        self.smtp_server_edit.setText("smtp.mail.yahoo.com")
        self.smtp_port_spin.setValue(587)
        self.smtp_security_combo.setCurrentText("STARTTLS (587)")
        
        if not self.imap_username_edit.text():
            self.imap_username_edit.setText(self.account.email_address)
        if not self.smtp_username_edit.text():
            self.smtp_username_edit.setText(self.account.email_address)
            
    def test_connection(self):
        """Test the connection with current settings."""
        # Create a test dialog
        test_dialog = QDialog(self)
        test_dialog.setWindowTitle("Connection Test")
        test_dialog.setModal(True)
        test_dialog.resize(400, 300)
        
        layout = QVBoxLayout(test_dialog)
        
        results = QTextEdit()
        results.setReadOnly(True)
        layout.addWidget(results)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(test_dialog.accept)
        layout.addWidget(close_btn)
        
        # Test with current form values
        results.append("Testing connection with current settings...\n")
        
        # Test IMAP
        imap_server = self.imap_server_edit.text()
        imap_port = self.imap_port_spin.value()
        imap_username = self.imap_username_edit.text()
        imap_password = self.imap_password_edit.text()
        
        if not imap_server:
            results.append("❌ IMAP test skipped: No server specified\n")
        elif not imap_username or not imap_password:
            results.append("❌ IMAP test skipped: Username or password missing\n")
        else:
            results.append(f"Testing IMAP: {imap_server}:{imap_port}")
            # Note: For security, we'd implement actual connection testing here
            results.append("⚠️ Connection test will be implemented after saving\n")
        
        # Test SMTP
        smtp_server = self.smtp_server_edit.text()
        smtp_port = self.smtp_port_spin.value()
        smtp_username = self.smtp_username_edit.text()
        smtp_password = self.smtp_password_edit.text()
        
        if not smtp_server:
            results.append("❌ SMTP test skipped: No server specified\n")
        elif not smtp_username or not smtp_password:
            results.append("❌ SMTP test skipped: Username or password missing\n")
        else:
            results.append(f"Testing SMTP: {smtp_server}:{smtp_port}")
            results.append("⚠️ Connection test will be implemented after saving\n")
            
        test_dialog.exec()
        
    def save_settings(self):
        """Save the server settings."""
        try:
            from ...data.models.accounts import SecurityType
            
            # Prepare updates dictionary
            updates = {}
            
            # IMAP settings
            updates['incoming_server'] = self.imap_server_edit.text().strip()
            updates['incoming_port'] = self.imap_port_spin.value()
            updates['incoming_username'] = self.imap_username_edit.text().strip()
            
            # Map security selection to SecurityType
            imap_security_text = self.imap_security_combo.currentText()
            if "TLS/SSL" in imap_security_text:
                updates['incoming_security'] = SecurityType.TLS_SSL
            elif "STARTTLS" in imap_security_text:
                updates['incoming_security'] = SecurityType.STARTTLS
            else:
                updates['incoming_security'] = SecurityType.NONE
            
            # SMTP settings
            updates['outgoing_server'] = self.smtp_server_edit.text().strip()
            updates['outgoing_port'] = self.smtp_port_spin.value()
            updates['outgoing_username'] = self.smtp_username_edit.text().strip()
            
            smtp_security_text = self.smtp_security_combo.currentText()
            if "TLS/SSL" in smtp_security_text:
                updates['outgoing_security'] = SecurityType.TLS_SSL
            elif "STARTTLS" in smtp_security_text:
                updates['outgoing_security'] = SecurityType.STARTTLS
            else:
                updates['outgoing_security'] = SecurityType.NONE
            
            # Passwords (if changed)
            imap_password = self.imap_password_edit.text()
            if imap_password:
                updates['incoming_password'] = imap_password
                
            smtp_password = self.smtp_password_edit.text()
            if smtp_password:
                updates['outgoing_password'] = smtp_password
            
            # Validate required fields
            if not updates.get('incoming_server'):
                QMessageBox.warning(self, "Validation Error", "IMAP server is required")
                return
                
            if not updates.get('outgoing_server'):
                QMessageBox.warning(self, "Validation Error", "SMTP server is required")
                return
            
            # Save to database using account manager
            if hasattr(self, 'account_manager') and self.account_manager:
                success = self.account_manager.repository.update_account(self.account.id, updates)
                
                if success:
                    QMessageBox.information(self, "Settings Saved", 
                                          "Server settings have been saved successfully!\n\n"
                                          f"IMAP: {updates['incoming_server']}:{updates['incoming_port']}\n"
                                          f"SMTP: {updates['outgoing_server']}:{updates['outgoing_port']}\n\n"
                                          "The account will now be able to connect to email servers.")
                    self.accept()
                else:
                    QMessageBox.warning(self, "Save Error", "Failed to save settings to database.")
            else:
                QMessageBox.critical(self, "Save Error", "Account manager not available for saving.")
            
        except Exception as e:
            logger.error(f"Failed to save server settings: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to save settings: {e}")


class AccountManagerDialog(QDialog):
    """Main account manager dialog."""
    
    accounts_changed = pyqtSignal()
    
    def __init__(self, account_manager: AccountManager, parent=None):
        super().__init__(parent)
        self.account_manager = account_manager
        
        self.setWindowTitle("Account Manager")
        self.setModal(True)
        self.resize(800, 600)
        
        self.setup_ui()
        self.load_accounts()
        
    def setup_ui(self):
        """Setup the account manager dialog UI."""
        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Account list
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        
        # Account list
        list_label = QLabel("Email Accounts")
        list_label.setFont(QFont("", 10, QFont.Weight.Bold))
        left_layout.addWidget(list_label)
        
        self.account_list = QListWidget()
        self.account_list.currentItemChanged.connect(self.on_account_selected)
        left_layout.addWidget(self.account_list)
        
        # Account list buttons
        list_buttons = QHBoxLayout()
        
        self.add_btn = QPushButton("Add Account")
        self.add_btn.clicked.connect(self.add_account)
        list_buttons.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("Edit Account")
        self.edit_btn.clicked.connect(self.edit_account)
        self.edit_btn.setEnabled(False)
        list_buttons.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("Delete Account")
        self.delete_btn.clicked.connect(self.delete_account)
        self.delete_btn.setEnabled(False)
        list_buttons.addWidget(self.delete_btn)
        
        left_layout.addLayout(list_buttons)
        
        splitter.addWidget(left_panel)
        
        # Right panel - Account details
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        
        details_label = QLabel("Account Details")
        details_label.setFont(QFont("", 10, QFont.Weight.Bold))
        right_layout.addWidget(details_label)
        
        # Account details
        self.details_group = QGroupBox("Selected Account")
        details_layout = QFormLayout(self.details_group)
        
        self.details_name = QLabel()
        details_layout.addRow("Name:", self.details_name)
        
        self.details_email = QLabel()
        details_layout.addRow("Email:", self.details_email)
        
        self.details_status = QLabel()
        details_layout.addRow("Status:", self.details_status)
        
        self.details_servers = QLabel()
        self.details_servers.setWordWrap(True)
        details_layout.addRow("Servers:", self.details_servers)
        
        self.details_last_sync = QLabel()
        details_layout.addRow("Last Sync:", self.details_last_sync)
        
        # Show stored credentials status
        self.credentials_status = QLabel()
        details_layout.addRow("Credentials:", self.credentials_status)
        
        right_layout.addWidget(self.details_group)
        
        # Quick actions
        actions_group = QGroupBox(_("email.account_manager.groups.quick_actions"))
        actions_layout = QVBoxLayout(actions_group)
        
        self.test_connection_btn = QPushButton(_("email.account_manager.buttons.test_connection"))
        self.test_connection_btn.clicked.connect(self.test_connection)
        self.test_connection_btn.setEnabled(False)
        actions_layout.addWidget(self.test_connection_btn)
        
        self.verify_credentials_btn = QPushButton(_("email.account_manager.buttons.verify_credentials"))
        self.verify_credentials_btn.clicked.connect(self.verify_credentials)
        self.verify_credentials_btn.setEnabled(False)
        actions_layout.addWidget(self.verify_credentials_btn)
        
        self.set_default_btn = QPushButton(_("email.account_manager.buttons.set_default"))
        self.set_default_btn.clicked.connect(self.set_default_account)
        self.set_default_btn.setEnabled(False)
        actions_layout.addWidget(self.set_default_btn)
        
        right_layout.addWidget(actions_group)
        right_layout.addStretch()
        
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([300, 500])
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.refresh_btn = QPushButton(_("email.account_manager.buttons.refresh"))
        self.refresh_btn.clicked.connect(self.load_accounts)
        button_layout.addWidget(self.refresh_btn)
        
        self.close_btn = QPushButton(_("email.account_manager.buttons.close"))
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        # Set final layout
        final_layout = QVBoxLayout()
        final_layout.addWidget(splitter)
        final_layout.addLayout(button_layout)
        self.setLayout(final_layout)
        
    def load_accounts(self):
        """Load all accounts into the list."""
        self.account_list.clear()
        
        try:
            accounts = self.account_manager.get_all_accounts(enabled_only=False)
            
            for account in accounts:
                item = QListWidgetItem()
                
                # Account display text
                display_text = account.name
                if account.is_default:
                    display_text += " (Default)"
                if not account.is_enabled:
                    display_text += " (Disabled)"
                    
                item.setText(display_text)
                item.setData(Qt.ItemDataRole.UserRole, account)
                    
                self.account_list.addItem(item)
                
        except Exception as e:
            QMessageBox.warning(self, _("email.account_manager.messages.error"), _("email.account_manager.messages.load_failed").format(error=str(e)))
            logger.error(f"Failed to load accounts: {e}")
            
    def on_account_selected(self, current, previous):
        """Handle account selection change."""
        if current:
            account = current.data(Qt.ItemDataRole.UserRole)
            self.show_account_details(account)
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.test_connection_btn.setEnabled(True)
            self.verify_credentials_btn.setEnabled(True)
            self.set_default_btn.setEnabled(not account.is_default)
        else:
            self.clear_account_details()
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.test_connection_btn.setEnabled(False)
            self.verify_credentials_btn.setEnabled(False)
            self.set_default_btn.setEnabled(False)
            
    def show_account_details(self, account: Account):
        """Show details for selected account."""
        self.details_name.setText(account.name or "")
        self.details_email.setText(account.email_address or "")
        
        status_text = account.connection_status or "Unknown"
        if not account.is_enabled:
            status_text += " (Disabled)"
        self.details_status.setText(status_text)
        
        # Show server configuration with proper error highlighting
        servers_text = ""
        if account.incoming_server:
            servers_text += f"IMAP: {account.incoming_server}:{account.incoming_port}\n"
        else:
            servers_text += "IMAP: ❌ NO SERVER CONFIGURED\n"
            
        if account.outgoing_server:
            servers_text += f"SMTP: {account.outgoing_server}:{account.outgoing_port}"
        else:
            servers_text += "SMTP: ❌ NO SERVER CONFIGURED"
            
        self.details_servers.setText(servers_text)
        
        if account.last_sync:
            self.details_last_sync.setText(account.last_sync.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self.details_last_sync.setText(_("email.account_manager.labels.never"))
            
        # Check stored credentials
        credential_manager = get_credential_manager()
        creds_status = []
        
        if account.incoming_password_key:
            try:
                password = credential_manager.retrieve_password(account.incoming_password_key)
                if password:
                    creds_status.append("IMAP: ✅ Stored")
                else:
                    creds_status.append("IMAP: ❌ Missing")
            except:
                creds_status.append("IMAP: ❌ Error")
        else:
            creds_status.append("IMAP: ⚠️ No key")
            
        if account.outgoing_password_key:
            try:
                password = credential_manager.retrieve_password(account.outgoing_password_key)
                if password:
                    creds_status.append("SMTP: ✅ Stored")
                else:
                    creds_status.append("SMTP: ❌ Missing")
            except:
                creds_status.append("SMTP: ❌ Error")
        else:
            creds_status.append("SMTP: ⚠️ No key")
            
        self.credentials_status.setText("\n".join(creds_status))
            
    def clear_account_details(self):
        """Clear account details display."""
        self.details_name.setText("")
        self.details_email.setText("")
        self.details_status.setText("")
        self.details_servers.setText("")
        self.details_last_sync.setText("")
        self.credentials_status.setText("")
        
    def add_account(self):
        """Add a new account."""
        from .account_setup_wizard import AccountSetupWizard
        
        wizard = AccountSetupWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            self.load_accounts()
            self.accounts_changed.emit()
            
    def edit_account(self):
        """Edit selected account with server configuration dialog."""
        current_item = self.account_list.currentItem()
        if not current_item:
            return
            
        account = current_item.data(Qt.ItemDataRole.UserRole)
        
        # Show server configuration dialog
        dialog = QuickServerConfigDialog(account, self)
        dialog.account_manager = self.account_manager  # Pass account manager for saving
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_accounts()
            self.accounts_changed.emit()
            
    def delete_account(self):
        """Delete selected account."""
        current_item = self.account_list.currentItem()
        if not current_item:
            return
            
        account = current_item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self,
            _("email.account_manager.buttons.delete_account"),
            _("email.account_manager.messages.delete_confirmation").format(name=account.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.account_manager.repository.delete_account(account.id)
                if success:
                    self.load_accounts()
                    self.accounts_changed.emit()
                    QMessageBox.information(self, _("email.account_manager.messages.success"), _("email.account_manager.messages.account_deleted"))
                else:
                    QMessageBox.warning(self, _("email.account_manager.messages.error"), _("email.account_manager.messages.delete_failed"))
                    
            except Exception as e:
                QMessageBox.critical(self, _("email.account_manager.messages.error"), _("email.account_manager.messages.delete_error").format(error=str(e)))
                
    def test_connection(self):
        """Test connection for selected account."""
        current_item = self.account_list.currentItem()
        if not current_item:
            return
            
        account = current_item.data(Qt.ItemDataRole.UserRole)
        
        # Create a simple test dialog
        test_dialog = QDialog(self)
        test_dialog.setWindowTitle("Connection Test")
        test_dialog.setModal(True)
        test_dialog.resize(500, 400)
        
        layout = QVBoxLayout(test_dialog)
        
        # Test results area
        results = QTextEdit()
        results.setReadOnly(True)
        layout.addWidget(results)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(test_dialog.accept)
        layout.addWidget(close_btn)
        
        # Run tests
        results.append(f"Testing connection for account: {account.name}\n")
        
        try:
            # Test IMAP
            results.append("Testing IMAP connection...")
            success, error = self.account_manager._test_incoming_connection(account)
            if success:
                results.append("✅ IMAP connection successful\n")
            else:
                results.append(f"❌ IMAP connection failed: {error}\n")
                
            # Test SMTP
            results.append("Testing SMTP connection...")
            success, error = self.account_manager._test_outgoing_connection(account)
            if success:
                results.append("✅ SMTP connection successful\n")
            else:
                results.append(f"❌ SMTP connection failed: {error}\n")
                
        except Exception as e:
            results.append(f"❌ Test error: {e}\n")
            
        results.append("Testing completed.")
        
        test_dialog.exec()
        
    def verify_credentials(self):
        """Verify stored credentials for selected account."""
        current_item = self.account_list.currentItem()
        if not current_item:
            return
            
        account = current_item.data(Qt.ItemDataRole.UserRole)
        credential_manager = get_credential_manager()
        
        # Create verification dialog
        verify_dialog = QDialog(self)
        verify_dialog.setWindowTitle(_("email.account_manager.titles.credential_verification"))
        verify_dialog.setModal(True)
        verify_dialog.resize(500, 400)
        
        layout = QVBoxLayout(verify_dialog)
        
        # Verification results
        results = QTextEdit()
        results.setReadOnly(True)
        layout.addWidget(results)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(verify_dialog.accept)
        layout.addWidget(close_btn)
        
        # Check credentials
        results.append(f"Verifying credentials for: {account.name}\n")
        
        # Check IMAP password
        if account.incoming_password_key:
            try:
                password = credential_manager.retrieve_password(account.incoming_password_key)
                if password:
                    results.append(f"✅ IMAP password found (length: {len(password)})")
                else:
                    results.append("❌ IMAP password not found in keyring")
            except Exception as e:
                results.append(f"❌ IMAP password error: {e}")
        else:
            results.append("⚠️ No IMAP password key configured")
            
        results.append("")
        
        # Check SMTP password
        if account.outgoing_password_key:
            try:
                password = credential_manager.retrieve_password(account.outgoing_password_key)
                if password:
                    results.append(f"✅ SMTP password found (length: {len(password)})")
                else:
                    results.append("❌ SMTP password not found in keyring")
            except Exception as e:
                results.append(f"❌ SMTP password error: {e}")
        else:
            results.append("⚠️ No SMTP password key configured")
            
        # Show account details
        results.append(f"\nAccount Details:")
        results.append(f"- Email: {account.email_address}")
        results.append(f"- IMAP Server: {account.incoming_server}:{account.incoming_port}")
        results.append(f"- IMAP Username: {account.incoming_username}")
        results.append(f"- SMTP Server: {account.outgoing_server}:{account.outgoing_port}")
        results.append(f"- SMTP Username: {account.outgoing_username}")
        
        verify_dialog.exec()
        
    def set_default_account(self):
        """Set selected account as default."""
        current_item = self.account_list.currentItem()
        if not current_item:
            return
            
        account = current_item.data(Qt.ItemDataRole.UserRole)
        
        try:
            success = self.account_manager.repository.set_default_account(account.id)
            if success:
                self.load_accounts()
                self.accounts_changed.emit()
                QMessageBox.information(self, _("email.account_manager.messages.success"), _("email.account_manager.messages.default_set").format(name=account.name))
            else:
                QMessageBox.warning(self, _("email.account_manager.messages.error"), _("email.account_manager.messages.default_failed"))
                
        except Exception as e:
            QMessageBox.critical(self, _("email.account_manager.messages.error"), _("email.account_manager.messages.default_error").format(error=str(e))) 