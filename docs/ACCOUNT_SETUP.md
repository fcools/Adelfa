# Account Setup Guide - Adelfa PIM Suite

## Overview

Adelfa's account setup wizard provides a comprehensive solution for configuring email, calendar, and contact synchronization accounts. The wizard supports automatic detection for major providers and manual configuration for custom servers.

## Features

### 🔍 Automatic Provider Detection
- **Supported Providers**: Gmail, Outlook.com, Hotmail, Yahoo Mail, iCloud
- **Protocol Detection**: Automatically detects IMAP, SMTP, CalDAV, and CardDAV settings
- **Security Configuration**: Handles TLS/SSL and STARTTLS encryption automatically

### 🔐 Secure Credential Storage
- **System Integration**: Uses your operating system's secure keyring
- **Multiple Credentials**: Separately stores passwords for email, calendar, and contacts
- **OAuth2 Support**: Ready for OAuth2 authentication (Gmail, Outlook)

### 🌍 Full Internationalization
- **14+ Languages**: English, Spanish, French, German, Italian, Portuguese, Russian, Chinese, Japanese, Korean
- **Automatic Detection**: Uses your system's locale settings
- **Manual Override**: Can be configured in application settings

### 📧 Multi-Protocol Support
- **Email Protocols**: IMAP, POP3, SMTP with automatic port and security detection
- **Calendar Sync**: CalDAV protocol for calendar synchronization
- **Contact Sync**: CardDAV protocol for contact synchronization

## How to Use

### Starting Account Setup

1. **From Main Menu**: File → Add Account...
2. **From Toolbar**: Click the "Add Account" button (if visible)
3. **First Time**: The wizard appears automatically if no accounts are configured

### Setup Process

#### Step 1: Provider Selection
- **Automatic Setup**: Enter your email address for automatic detection
- **Manual Setup**: Choose this for custom or corporate servers
- **Detection**: Click "Detect Settings" to automatically find server configurations

#### Step 2: Account Details
- **Account Name**: A friendly name for this account (e.g., "Work Email")
- **Display Name**: Your name as it appears in outgoing emails
- **Credentials**: Username and password with optional secure storage
- **Connection Test**: Verify settings before proceeding

#### Step 3: Server Settings (Manual Setup Only)
- **Incoming Mail**: IMAP/POP3 server settings
- **Outgoing Mail**: SMTP server configuration
- **Security**: TLS/SSL or STARTTLS encryption options
- **Ports**: Standard ports are pre-filled but can be customized

#### Step 4: Calendar & Contacts
- **Calendar Sync**: Enable CalDAV synchronization
- **Contact Sync**: Enable CardDAV synchronization
- **Sync Frequency**: Choose how often to synchronize data
- **Auto-Detection**: Automatically detect settings for known providers

#### Step 5: Summary
- **Review**: Confirm all settings before creating the account
- **Completion**: Account is created and credentials are stored securely

## Supported Providers

### Major Email Providers

| Provider | Email | Calendar | Contacts | Notes |
|----------|-------|----------|----------|-------|
| Gmail | ✅ IMAP/SMTP | ✅ CalDAV | ✅ CardDAV | Manual |
| Outlook.com | ✅ IMAP/SMTP | ✅ Exchange/CalDAV | ⚠️ Exchange only | Manual |
| Yahoo Mail | ✅ IMAP/SMTP | ✅ CalDAV | ✅ CardDAV | Manual |
| iCloud | ✅ IMAP/SMTP | ✅ CalDAV | ✅ CardDAV | Manual |
| Custom/Corporate | ✅ Manual Setup | ✅ Manual CalDAV | ✅ Manual CardDAV | Manual |

### Authentication Methods
- **Standard Password**: Username and password authentication
- **OAuth2**: Modern authentication for Google and Microsoft accounts
- **App Passwords**: For providers requiring app-specific passwords

## Configuration Examples

### Gmail Setup
```
Email: your.email@gmail.com
IMAP: imap.gmail.com:993 (TLS/SSL)
SMTP: smtp.gmail.com:587 (STARTTLS)
CalDAV: https://apidata.googleusercontent.com/caldav/v2/
CardDAV: https://www.google.com/.well-known/carddav
```

### Outlook.com Setup
```
Email: your.email@outlook.com
IMAP: outlook.office365.com:993 (TLS/SSL)
SMTP: smtp-mail.outlook.com:587 (STARTTLS)
CalDAV: https://outlook.office365.com/EWS/Exchange.asmx
CardDAV: Exchange Web Services (automatic)
```

### Corporate Exchange Setup
```
Email: your.email@company.com
IMAP: mail.company.com:993 (TLS/SSL)
SMTP: smtp.company.com:587 (STARTTLS)
CalDAV: https://mail.company.com/EWS/Exchange.asmx
CardDAV: https://mail.company.com/EWS/Exchange.asmx
```

## Account Management

### Managing Existing Accounts
- **View Accounts**: File → Account Settings...
- **Default Account**: Set which account is used by default for new emails
- **Enable/Disable**: Temporarily disable accounts without deleting them
- **Test Connections**: Verify that account settings are still working

### Account Security
- **Password Changes**: Update stored passwords when they change
- **Credential Cleanup**: Passwords are securely deleted when accounts are removed
- **Connection Status**: Monitor whether accounts are successfully connecting

### Troubleshooting

#### Common Issues
1. **Authentication Failed**
   - Verify username and password are correct
   - Check if two-factor authentication is enabled
   - Use app-specific passwords if required

2. **Connection Timeout**
   - Verify server addresses and ports
   - Check firewall and network connectivity
   - Try different security settings (TLS vs STARTTLS)

3. **Calendar/Contact Sync Issues**
   - Ensure CalDAV/CardDAV URLs are correct
   - Verify permissions for calendar/contact access
   - Check if the provider supports the protocols

#### Error Messages
- **"Server not found"**: Check server address spelling and network connection
- **"SSL/TLS error"**: Try different security settings or check certificates
- **"Authentication failed"**: Verify credentials and authentication method

## Technical Details

### Supported Protocols
- **IMAP4**: Full IMAP4rev1 support with IDLE for real-time updates
- **POP3**: POP3 with optional STLS encryption
- **SMTP**: SMTP with AUTH and STARTTLS support
- **CalDAV**: RFC 4791 calendar synchronization
- **CardDAV**: RFC 6352 contact synchronization

### Security Features
- **Keyring Integration**: Uses platform-specific secure storage
  - Linux: Secret Service API (GNOME Keyring, KWallet)
  - Windows: Windows Credential Manager
  - macOS: Keychain Services
- **Encrypted Storage**: All passwords and tokens are encrypted at rest
- **Connection Security**: Supports TLS 1.2+ with certificate validation

### Database Integration
- **Account Storage**: SQLAlchemy models with comprehensive account information
- **Relationship Mapping**: Links accounts to emails, events, and contacts
- **Migration Support**: Alembic database migrations for schema updates
- **Connection Testing**: Tracks connection test results and account status

## Next Steps

After setting up your accounts:

1. **Email**: Start receiving and sending emails
2. **Calendar**: Sync events and create meetings
3. **Contacts**: Import and manage your address book
4. **Integration**: Create calendar events with contact attendees
5. **Collaboration**: Use Jitsi Meet integration for video calls

For more information, see the main [PLANNING.md](../PLANNING.md) document. 