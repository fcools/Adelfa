"""
Protocol detection and connection testing for Adelfa PIM suite.

Automatically detects email server settings (IMAP/POP3/SMTP) and
calendar/contact server settings (CalDAV/CardDAV) for common providers.
"""

import imaplib
import poplib
import smtplib
import socket
import ssl
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import dns.resolver
import requests
from urllib.parse import urljoin, urlparse

from ...utils.logging_setup import get_logger
from ...data.models.accounts import SecurityType, EmailProtocol, AuthMethod

logger = get_logger(__name__)


@dataclass
class ServerSettings:
    """Server configuration settings."""
    server: str
    port: int
    security: SecurityType
    protocol: Optional[EmailProtocol] = None
    auth_method: AuthMethod = AuthMethod.PASSWORD


@dataclass
class DetectionResult:
    """Result of protocol detection."""
    success: bool
    email_settings: Optional[Dict[str, ServerSettings]] = None
    caldav_url: Optional[str] = None
    carddav_url: Optional[str] = None
    error_message: Optional[str] = None
    provider_name: Optional[str] = None


class ProtocolDetector:
    """
    Detects email, calendar, and contact server settings.
    
    Provides automatic detection of server configurations for common
    providers and generic discovery mechanisms for others.
    """
    
    # Common provider configurations
    PROVIDER_CONFIGS = {
        "gmail.com": {
            "name": "Gmail",
            "imap": ServerSettings("imap.gmail.com", 993, SecurityType.TLS_SSL),
            "smtp": ServerSettings("smtp.gmail.com", 587, SecurityType.STARTTLS),
            "caldav": "https://apidata.googleusercontent.com/caldav/v2/",
            "carddav": "https://www.google.com/.well-known/carddav",
            "auth_method": AuthMethod.OAUTH2
        },
        "outlook.com": {
            "name": "Outlook.com",
            "imap": ServerSettings("outlook.office365.com", 993, SecurityType.TLS_SSL),
            "smtp": ServerSettings("smtp-mail.outlook.com", 587, SecurityType.STARTTLS),
            "caldav": "https://outlook.office365.com/EWS/Exchange.asmx",
            "carddav": None,  # Uses Exchange Web Services
            "auth_method": AuthMethod.OAUTH2
        },
        "hotmail.com": {
            "name": "Hotmail",
            "imap": ServerSettings("outlook.office365.com", 993, SecurityType.TLS_SSL),
            "smtp": ServerSettings("smtp-mail.outlook.com", 587, SecurityType.STARTTLS),
            "caldav": "https://outlook.office365.com/EWS/Exchange.asmx",
            "carddav": None,
            "auth_method": AuthMethod.OAUTH2
        },
        "yahoo.com": {
            "name": "Yahoo Mail",
            "imap": ServerSettings("imap.mail.yahoo.com", 993, SecurityType.TLS_SSL),
            "smtp": ServerSettings("smtp.mail.yahoo.com", 587, SecurityType.STARTTLS),
            "caldav": "https://caldav.calendar.yahoo.com/",
            "carddav": "https://carddav.address.yahoo.com/",
            "auth_method": AuthMethod.PASSWORD
        },
        "icloud.com": {
            "name": "iCloud",
            "imap": ServerSettings("imap.mail.me.com", 993, SecurityType.TLS_SSL),
            "smtp": ServerSettings("smtp.mail.me.com", 587, SecurityType.STARTTLS),
            "caldav": "https://caldav.icloud.com/",
            "carddav": "https://contacts.icloud.com/",
            "auth_method": AuthMethod.PASSWORD
        },
        "me.com": {
            "name": "iCloud",
            "imap": ServerSettings("imap.mail.me.com", 993, SecurityType.TLS_SSL),
            "smtp": ServerSettings("smtp.mail.me.com", 587, SecurityType.STARTTLS),
            "caldav": "https://caldav.icloud.com/",
            "carddav": "https://contacts.icloud.com/",
            "auth_method": AuthMethod.PASSWORD
        }
    }
    
    # Common port combinations to try
    IMAP_PORTS = [(993, SecurityType.TLS_SSL), (143, SecurityType.STARTTLS), (143, SecurityType.NONE)]
    POP3_PORTS = [(995, SecurityType.TLS_SSL), (110, SecurityType.STARTTLS), (110, SecurityType.NONE)]
    SMTP_PORTS = [(587, SecurityType.STARTTLS), (465, SecurityType.TLS_SSL), (25, SecurityType.NONE)]
    
    def __init__(self):
        """Initialize the protocol detector."""
        self.logger = logger
        self.timeout = 10  # seconds
    
    def detect_settings(self, email_address: str) -> DetectionResult:
        """
        Detect server settings for an email address.
        
        Args:
            email_address: Email address to detect settings for
        
        Returns:
            DetectionResult: Detection results
        """
        try:
            domain = email_address.split('@')[1].lower()
            
            # Check if we have predefined settings for this domain
            if domain in self.PROVIDER_CONFIGS:
                return self._get_predefined_settings(domain)
            
            # Try generic detection
            return self._detect_generic_settings(domain)
            
        except Exception as e:
            self.logger.error(f"Failed to detect settings for {email_address}: {e}")
            return DetectionResult(
                success=False,
                error_message=f"Detection failed: {str(e)}"
            )
    
    def _get_predefined_settings(self, domain: str) -> DetectionResult:
        """Get predefined settings for known providers."""
        try:
            config = self.PROVIDER_CONFIGS[domain]
            
            email_settings = {}
            if "imap" in config:
                email_settings["imap"] = config["imap"]
            if "smtp" in config:
                email_settings["smtp"] = config["smtp"]
            
            return DetectionResult(
                success=True,
                email_settings=email_settings,
                caldav_url=config.get("caldav"),
                carddav_url=config.get("carddav"),
                provider_name=config["name"]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get predefined settings for {domain}: {e}")
            return DetectionResult(
                success=False,
                error_message=f"Failed to get predefined settings: {str(e)}"
            )
    
    def _detect_generic_settings(self, domain: str) -> DetectionResult:
        """Detect settings using generic methods."""
        try:
            email_settings = {}
            
            # Try to detect IMAP settings
            imap_settings = self._detect_imap_settings(domain)
            if imap_settings:
                email_settings["imap"] = imap_settings
            
            # Try to detect SMTP settings
            smtp_settings = self._detect_smtp_settings(domain)
            if smtp_settings:
                email_settings["smtp"] = smtp_settings
            
            # Try to detect CalDAV/CardDAV settings
            caldav_url, carddav_url = self._detect_dav_settings(domain)
            
            if email_settings or caldav_url or carddav_url:
                return DetectionResult(
                    success=True,
                    email_settings=email_settings if email_settings else None,
                    caldav_url=caldav_url,
                    carddav_url=carddav_url
                )
            else:
                return DetectionResult(
                    success=False,
                    error_message="Could not detect any server settings"
                )
                
        except Exception as e:
            self.logger.error(f"Generic detection failed for {domain}: {e}")
            return DetectionResult(
                success=False,
                error_message=f"Generic detection failed: {str(e)}"
            )
    
    def _detect_imap_settings(self, domain: str) -> Optional[ServerSettings]:
        """Detect IMAP server settings."""
        # Try common IMAP server names
        server_candidates = [
            f"imap.{domain}",
            f"mail.{domain}",
            f"mx.{domain}",
            domain
        ]
        
        for server in server_candidates:
            for port, security in self.IMAP_PORTS:
                if self._test_imap_connection(server, port, security):
                    return ServerSettings(server, port, security, EmailProtocol.IMAP)
        
        return None
    
    def _detect_smtp_settings(self, domain: str) -> Optional[ServerSettings]:
        """Detect SMTP server settings."""
        # Try common SMTP server names
        server_candidates = [
            f"smtp.{domain}",
            f"mail.{domain}",
            f"mx.{domain}",
            domain
        ]
        
        for server in server_candidates:
            for port, security in self.SMTP_PORTS:
                if self._test_smtp_connection(server, port, security):
                    return ServerSettings(server, port, security)
        
        return None
    
    def _detect_dav_settings(self, domain: str) -> Tuple[Optional[str], Optional[str]]:
        """Detect CalDAV and CardDAV server settings."""
        caldav_url = None
        carddav_url = None
        
        # Try well-known URIs (RFC 5785)
        base_urls = [f"https://{domain}", f"https://mail.{domain}"]
        
        for base_url in base_urls:
            # Try CalDAV well-known URI
            caldav_candidate = urljoin(base_url, "/.well-known/caldav")
            if self._test_url_accessibility(caldav_candidate):
                caldav_url = caldav_candidate
            
            # Try CardDAV well-known URI
            carddav_candidate = urljoin(base_url, "/.well-known/carddav")
            if self._test_url_accessibility(carddav_candidate):
                carddav_url = carddav_candidate
        
        return caldav_url, carddav_url
    
    def _test_imap_connection(self, server: str, port: int, security: SecurityType) -> bool:
        """Test IMAP connection."""
        try:
            if security == SecurityType.TLS_SSL:
                conn = imaplib.IMAP4_SSL(server, port, timeout=self.timeout)
            else:
                conn = imaplib.IMAP4(server, port, timeout=self.timeout)
                if security == SecurityType.STARTTLS:
                    conn.starttls()
            
            conn.logout()
            return True
            
        except Exception:
            return False
    
    def _test_smtp_connection(self, server: str, port: int, security: SecurityType) -> bool:
        """Test SMTP connection."""
        try:
            if security == SecurityType.TLS_SSL:
                conn = smtplib.SMTP_SSL(server, port, timeout=self.timeout)
            else:
                conn = smtplib.SMTP(server, port, timeout=self.timeout)
                if security == SecurityType.STARTTLS:
                    conn.starttls()
            
            conn.quit()
            return True
            
        except Exception:
            return False
    
    def _test_url_accessibility(self, url: str) -> bool:
        """Test if a URL is accessible."""
        try:
            response = requests.get(url, timeout=self.timeout, verify=True)
            return response.status_code in [200, 301, 302, 401]  # 401 might indicate auth required
            
        except Exception:
            return False
    
    def test_connection(self, settings: ServerSettings, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Test connection with credentials.
        
        Args:
            settings: Server settings to test
            username: Username for authentication
            password: Password for authentication
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if settings.protocol == EmailProtocol.IMAP:
                return self._test_imap_auth(settings, username, password)
            elif settings.protocol == EmailProtocol.POP3:
                return self._test_pop3_auth(settings, username, password)
            else:  # SMTP
                return self._test_smtp_auth(settings, username, password)
                
        except Exception as e:
            return False, str(e)
    
    def _test_imap_auth(self, settings: ServerSettings, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Test IMAP authentication."""
        try:
            if settings.security == SecurityType.TLS_SSL:
                conn = imaplib.IMAP4_SSL(settings.server, settings.port, timeout=self.timeout)
            else:
                conn = imaplib.IMAP4(settings.server, settings.port, timeout=self.timeout)
                if settings.security == SecurityType.STARTTLS:
                    conn.starttls()
            
            conn.login(username, password)
            conn.logout()
            return True, None
            
        except imaplib.IMAP4.error as e:
            error_msg = str(e).lower()
            if "authentication failed" in error_msg:
                return False, "Authentication failed. Please check your credentials."
            elif "invalid credentials" in error_msg:
                return False, "Invalid credentials."
            else:
                return False, f"IMAP error: {str(e)}"
                
        except socket.timeout:
            return False, "Connection timed out."
            
        except socket.gaierror:
            return False, "Server not found. Please check the server address."
            
        except ssl.SSLError as e:
            return False, f"SSL/TLS error: {str(e)}"
            
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def _test_pop3_auth(self, settings: ServerSettings, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Test POP3 authentication."""
        try:
            if settings.security == SecurityType.TLS_SSL:
                conn = poplib.POP3_SSL(settings.server, settings.port, timeout=self.timeout)
            else:
                conn = poplib.POP3(settings.server, settings.port, timeout=self.timeout)
                if settings.security == SecurityType.STARTTLS:
                    conn.stls()
            
            conn.user(username)
            conn.pass_(password)
            conn.quit()
            return True, None
            
        except poplib.error_proto as e:
            error_msg = str(e).lower()
            if "authentication failed" in error_msg or "invalid" in error_msg:
                return False, "Authentication failed. Please check your credentials."
            else:
                return False, f"POP3 error: {str(e)}"
                
        except socket.timeout:
            return False, "Connection timed out."
            
        except socket.gaierror:
            return False, "Server not found. Please check the server address."
            
        except ssl.SSLError as e:
            return False, f"SSL/TLS error: {str(e)}"
            
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def _test_smtp_auth(self, settings: ServerSettings, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Test SMTP authentication."""
        try:
            if settings.security == SecurityType.TLS_SSL:
                conn = smtplib.SMTP_SSL(settings.server, settings.port, timeout=self.timeout)
            else:
                conn = smtplib.SMTP(settings.server, settings.port, timeout=self.timeout)
                if settings.security == SecurityType.STARTTLS:
                    conn.starttls()
            
            conn.login(username, password)
            conn.quit()
            return True, None
            
        except smtplib.SMTPAuthenticationError:
            return False, "Authentication failed. Please check your credentials."
            
        except smtplib.SMTPRecipientsRefused:
            return False, "Authentication failed."
            
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {str(e)}"
            
        except socket.timeout:
            return False, "Connection timed out."
            
        except socket.gaierror:
            return False, "Server not found. Please check the server address."
            
        except ssl.SSLError as e:
            return False, f"SSL/TLS error: {str(e)}"
            
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def test_caldav_connection(self, server_url: str, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Test CalDAV connection."""
        try:
            # Basic HTTP authentication test
            response = requests.get(
                server_url,
                auth=(username, password),
                timeout=self.timeout,
                verify=True
            )
            
            if response.status_code == 200:
                return True, None
            elif response.status_code == 401:
                return False, "Authentication failed. Please check your credentials."
            else:
                return False, f"Server returned status code: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "Connection timed out."
            
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to server. Please check the URL."
            
        except requests.exceptions.SSLError as e:
            return False, f"SSL/TLS error: {str(e)}"
            
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def test_carddav_connection(self, server_url: str, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Test CardDAV connection."""
        # For now, use the same logic as CalDAV
        return self.test_caldav_connection(server_url, username, password) 