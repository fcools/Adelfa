# Adelfa Email Client

<div align="center">

![Adelfa Logo](docs/assets/logo.png)
*Modern email client for Linux with Outlook 365 familiarity*

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://pypi.org/project/PyQt6/)

</div>

## 🎯 Overview

**Adelfa** is an open-source email client designed specifically to help Windows users transition smoothly to Linux. It provides an Outlook 365-like interface and behavior while maintaining modern Linux compatibility and performance.

### 🔑 Key Features

- **Outlook 365 Familiar Interface**: Recognizable layout and styling for Windows migrants
- **Precise Font Control**: Point-size font selection (8pt, 10pt, 12pt, etc.) like Outlook
- **Cross-Platform Compatibility**: Runs on all Linux distributions via AppImage
- **Internationalization**: Automatic system locale detection with multi-language support
- **Modern Performance**: Fast, responsive, and memory-efficient
- **Rich Text Editing**: WYSIWYG HTML email composition
- **Multiple Account Support**: IMAP, POP3, and SMTP protocol support

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- PyQt6 development libraries
- Linux distribution (Ubuntu, Fedora, Arch, openSUSE, etc.)

### Installation from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/adelfa.git
cd adelfa

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On bash/zsh
# or
source venv/bin/activate.fish  # On fish shell

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py
```

### Build AppImage

```bash
# Clone the repository
git clone https://github.com/yourusername/adelfa.git
cd adelfa

# Create virtual environment and install dependencies
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Build the AppImage
./scripts/build_appimage_manual.sh

# Run the AppImage
chmod +x Adelfa-0.1.0-dev-x86_64.AppImage
./Adelfa-0.1.0-dev-x86_64.AppImage
```

## 🏗️ Architecture

Adelfa is built with modern Python and Qt technologies:

- **Frontend**: PyQt6 for native Linux performance
- **Backend**: Python 3.11+ with type hints and async support
- **Email Protocols**: Built-in IMAP, POP3, SMTP support
- **Database**: SQLite for local storage
- **Configuration**: TOML-based configuration files
- **Security**: Keyring integration for secure credential storage

## 🎨 Design Philosophy

### Why Not Just Use Thunderbird?

While Thunderbird is excellent and standards-compliant, it presents challenges for Windows users migrating to Linux:

1. **Font Sizing**: Thunderbird doesn't support point-size font selection, causing formatting issues with Outlook-composed emails
2. **Interface Differences**: The UI paradigms differ significantly from Outlook 365
3. **Workflow Disruption**: Different keyboard shortcuts and menu organizations

### Adelfa's Approach

- **Outlook Compatibility First**: Handle non-standard Outlook behaviors gracefully
- **Familiar Interface**: Use Outlook 365 visual patterns and workflows
- **Linux Native**: Full integration with Linux desktop environments
- **Standards Compliant**: Support email standards while being pragmatic about compatibility

## 🛠️ Development

### Setting Up Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
pylint src/
```

### Project Structure

```
adelfa/
├── src/
│   ├── adelfa/
│   │   ├── core/          # Core email functionality
│   │   ├── gui/           # UI components and windows
│   │   ├── protocols/     # Email protocol handlers
│   │   ├── data/          # Database models and storage
│   │   ├── utils/         # Utility functions
│   │   └── config/        # Configuration management
│   └── resources/         # Icons, themes, templates
├── tests/                 # Unit tests
├── docs/                  # Documentation
├── scripts/               # Build and packaging scripts
└── appimage/              # AppImage packaging files
```

### Contributing

1. Read our [Contributing Guidelines](CONTRIBUTING.md)
2. Check the [Task Board](TASK.md) for current priorities
3. Fork the repository and create a feature branch
4. Write tests for new functionality
5. Ensure code follows our style guidelines
6. Submit a pull request

## 🔍 Current Status

**Status**: Early Development (Phase 1)

### Completed
- ✅ Project architecture and planning
- ✅ Development environment setup
- ✅ Initial project structure
- ✅ Core GUI framework with 3-pane layout
- ✅ AppImage packaging system
- ✅ Internationalization and locale support

### In Progress
- 🔄 Email protocol handlers
- 🔄 Rich text editor with point-size fonts
- 🔄 Configuration management

### Planned
- 📋 Account setup wizard
- 📋 Message threading and conversation view
- 📋 Contact management
- 📋 Calendar integration

## 📋 Roadmap

### Phase 1: MVP (Q1 2024)
- Basic email reading and composition
- IMAP/POP3/SMTP support
- Outlook-style font point-size selection
- 3-pane interface layout

### Phase 2: Outlook Compatibility (Q2 2024)
- Advanced rich text editing
- Signature management
- Contact integration
- PST file import (read-only)

### Phase 3: Advanced Features (Q3 2024)
- PGP/GPG encryption
- Calendar integration
- Plugin system
- Advanced filtering

## 🤝 Community

- **Bug Reports**: [GitHub Issues](https://github.com/yourusername/adelfa/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/yourusername/adelfa/discussions)
- **Documentation**: [Wiki](https://github.com/yourusername/adelfa/wiki)

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- The Thunderbird team for inspiration and email client best practices
- The Qt and PyQt communities for excellent GUI framework support
- Microsoft Outlook team for establishing user experience patterns
- The Linux community for supporting open-source alternatives

---

<div align="center">
<strong>Help Windows users feel at home on Linux</strong><br>
Star ⭐ this repository if you support the mission!
</div> 