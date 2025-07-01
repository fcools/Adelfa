# Adelfa Email Client - Translations

This directory contains translation files for the Adelfa email client.

## File Format

Translation files use Qt's binary translation format (`.qm` files), which are compiled from Qt Linguist source files (`.ts` files).

## File Naming Convention

Translation files should be named according to the pattern:
- `adelfa_{locale}.qm` - for specific locale (e.g., `adelfa_es_ES.qm` for Spanish Spain)
- `adelfa_{language}.qm` - for language only (e.g., `adelfa_es.qm` for Spanish)

## Supported Locales

The application supports the following locales:
- `en_US` - English (United States) - Default, no translation file needed
- `en_GB` - English (United Kingdom)
- `es_ES` - Spanish (Spain)
- `es_MX` - Spanish (Mexico)
- `fr_FR` - French (France)
- `de_DE` - German (Germany)
- `it_IT` - Italian (Italy)
- `pt_BR` - Portuguese (Brazil)
- `pt_PT` - Portuguese (Portugal)
- `ru_RU` - Russian (Russia)
- `zh_CN` - Chinese (Simplified)
- `zh_TW` - Chinese (Traditional)
- `ja_JP` - Japanese (Japan)
- `ko_KR` - Korean (South Korea)

## How It Works

1. **Automatic Detection**: The application automatically detects the system locale from environment variables (`LANG`, `LC_ALL`, `LC_MESSAGES`) or Qt's locale detection.

2. **Fallback Chain**: If a specific locale isn't found (e.g., `es_MX`), the application tries the language code only (`es`), then falls back to English.

3. **Configuration Override**: Users can override the automatic detection by setting the `language` option in their `adelfa.toml` configuration file:
   ```toml
   [ui]
   language = "es_ES"  # Force Spanish (Spain)
   # or
   language = "auto"   # Use system locale (default)
   ```

## Creating Translations

To create translations for Adelfa:

1. **Extract translatable strings** (for developers):
   ```bash
   # This would extract strings from Python files into a .ts file
   pylupdate5 -verbose src/adelfa/**/*.py -ts adelfa_es.ts
   ```

2. **Translate the strings** using Qt Linguist:
   ```bash
   linguist adelfa_es.ts
   ```

3. **Compile to binary format**:
   ```bash
   lrelease adelfa_es.ts -qm adelfa_es.qm
   ```

4. **Place the .qm file** in this directory

## Testing Translations

To test a translation:

1. Set your system locale or configure Adelfa to use the specific language
2. Start Adelfa - it should automatically load the appropriate translation
3. Check the logs for translation loading messages

## Current Status

- ✅ Locale detection system implemented
- ✅ Qt translation loading system implemented  
- ✅ Configuration support for language override
- ⏳ Translation files creation (community contributions welcome)
- ⏳ Translation extraction scripts
- ⏳ Automated translation workflow

## Contributing Translations

We welcome community contributions for translations! Please:

1. Check if your language is in the supported locales list
2. Contact the development team to coordinate translation efforts
3. Follow the Qt Linguist workflow described above
4. Submit translation files via pull request

For questions about translations, please open an issue on the project repository. 