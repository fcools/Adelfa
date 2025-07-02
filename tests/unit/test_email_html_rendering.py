"""
Unit tests for email HTML rendering and CSS support.

Tests the HTML cleaning and rendering capabilities of the MessagePreviewWidget
to ensure emails display correctly with modern CSS while maintaining security.
"""

import sys
import os
import unittest

# Set up path to import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

# Import QtWebEngineWidgets before creating QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QUrl

# Only create QApplication after WebEngine imports
if not QApplication.instance():
    app = QApplication(sys.argv)

from adelfa.gui.email.email_view import MessagePreviewWidget
from adelfa.core.email.imap_client import EmailMessage, EmailHeader
from unittest.mock import Mock, patch


class TestEmailHTMLRendering(unittest.TestCase):
    """Test email HTML rendering and layout preservation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.preview_widget = MessagePreviewWidget()
        self.preview_widget.cache_manager = Mock()
        self.preview_widget.config = Mock()
        self.preview_widget.config.security.external_images = "ask"
        self.preview_widget.config.security.external_links = "ask"
    
    def test_html_cleaning_preserves_layout_elements(self):
        """Test that HTML cleaning preserves important layout elements."""
        # Test HTML with table layout (common in emails)
        html_content = """
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="padding: 10px;">
                    <h2>Email Title</h2>
                    <p>This is a <strong>test email</strong> with formatting.</p>
                    <div style="background-color: #f0f0f0; padding: 15px;">
                        <img src="https://example.com/image.jpg" width="200" height="100" alt="Test Image">
                    </div>
                </td>
            </tr>
        </table>
        """
        
        cleaned_html = self.preview_widget._clean_html_content(html_content)
        
        # Verify that table structure is preserved
        self.assertIn('<table', cleaned_html)
        self.assertIn('<tr>', cleaned_html)
        self.assertIn('<td', cleaned_html)
        self.assertTrue('width="100%"' in cleaned_html or 'style="width: 100%' in cleaned_html)
        
        # Verify that text formatting is preserved
        self.assertIn('<h2>', cleaned_html)
        self.assertIn('<strong>', cleaned_html)
        self.assertIn('<p>', cleaned_html)
        self.assertIn('<div', cleaned_html)
        
        # Verify that styling is preserved
        self.assertTrue('padding:' in cleaned_html or 'padding: ' in cleaned_html)
        self.assertTrue('background-color:' in cleaned_html or 'background-color: ' in cleaned_html)
        
        # Verify wrapper div is added
        self.assertIn('email-wrapper', cleaned_html)
    
    def test_html_cleaning_removes_dangerous_elements(self):
        """Test that HTML cleaning removes dangerous elements while preserving layout."""
        dangerous_html = """
        <table width="100%">
            <tr>
                <td>
                    <script>alert('dangerous');</script>
                    <p onclick="malicious()">Click me</p>
                    <img src="https://example.com/image.jpg" onload="evil()" width="100">
                    <div style="background: url(safe-image.jpg);">Content</div>
                </td>
            </tr>
        </table>
        """
        
        cleaned_html = self.preview_widget._clean_html_content(dangerous_html)
        
        # Verify dangerous elements are removed
        self.assertNotIn('<script>', cleaned_html)
        self.assertTrue('onclick=' not in cleaned_html)
        self.assertTrue('onload=' not in cleaned_html)
        self.assertNotIn('alert(', cleaned_html)
        self.assertNotIn('malicious()', cleaned_html)
        
        # Verify safe layout elements are preserved
        self.assertIn('<table', cleaned_html)
        self.assertIn('<tr>', cleaned_html)
        self.assertIn('<td>', cleaned_html)
        self.assertIn('<p>', cleaned_html)
        self.assertIn('<img', cleaned_html)
        self.assertIn('<div', cleaned_html)
        self.assertTrue('width=' in cleaned_html)
        self.assertTrue('background:' in cleaned_html or 'background-' in cleaned_html)
    
    def test_image_placeholder_preserves_dimensions(self):
        """Test that image placeholders preserve original dimensions."""
        html_with_images = """
        <div>
            <img src="https://example.com/large-banner.jpg" width="600" height="200" alt="Banner">
            <img src="https://example.com/small-icon.jpg" width="32" height="32" alt="Icon">
        </div>
        """
        
        # Process HTML without loading images
        processed_html = self.preview_widget._process_html_content(html_with_images, load_images=False, enable_links=False)
        
        # Check that placeholder maintains dimensions
        self.assertTrue('width="600"' in processed_html)
        self.assertTrue('height="200"' in processed_html)
        self.assertTrue('width="32"' in processed_html)
        self.assertTrue('height="32"' in processed_html)
        
        # Check that placeholders are data URLs
        self.assertIn('data:image/svg+xml;base64,', processed_html)
        
        # Check that original accessibility attributes are preserved (better than overriding)
        self.assertTrue('alt="Banner"' in processed_html)
        self.assertTrue('alt="Icon"' in processed_html)
        
        # Check that privacy information is in the title attribute
        self.assertTrue('title="Image blocked for privacy' in processed_html)
    
    def test_image_loading_preserves_structure(self):
        """Test that image loading preserves HTML structure."""
        html_with_images = """
        <div style="text-align: center;">
            <img src="https://example.com/image.jpg" width="300" height="200" style="border: 1px solid #ccc;" alt="Test">
        </div>
        """
        
        with patch('requests.get') as mock_get:
            # Mock successful image download
            mock_response = Mock()
            mock_response.headers = {'content-type': 'image/jpeg'}
            mock_response.iter_content.return_value = [b'fake_image_data']
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # Process HTML with image loading enabled
            processed_html = self.preview_widget._process_html_content(html_with_images, load_images=True, enable_links=False)
            
            # Verify structure is preserved
            self.assertTrue('<div style="text-align: center;">' in processed_html)
            self.assertTrue('width="300"' in processed_html)
            self.assertTrue('height="200"' in processed_html)
            self.assertIn('border: 1px solid #ccc', processed_html)
            self.assertTrue('alt="Test"' in processed_html)
            
            # Verify image is converted to data URL
            self.assertIn('data:image/jpeg;base64,', processed_html)
    
    def test_css_styles_are_preserved(self):
        """Test that CSS styles in email are properly preserved."""
        html_with_styles = """
        <div style="font-family: Arial, sans-serif; color: #333;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background-color: #f5f5f5;">
                    <td style="padding: 15px; border: 1px solid #ddd;">
                        <h2 style="color: #0066cc; margin: 0 0 10px 0;">Title</h2>
                        <p style="line-height: 1.6; margin: 0;">Content with styling.</p>
                    </td>
                </tr>
            </table>
        </div>
        """
        
        cleaned_html = self.preview_widget._clean_html_content(html_with_styles)
        
        # Verify all CSS styles are preserved
        self.assertIn('font-family: Arial, sans-serif', cleaned_html)
        self.assertIn('color: #333', cleaned_html)
        self.assertIn('width: 100%', cleaned_html)
        self.assertIn('border-collapse: collapse', cleaned_html)
        self.assertIn('background-color: #f5f5f5', cleaned_html)
        self.assertIn('padding: 15px', cleaned_html)
        self.assertIn('border: 1px solid #ddd', cleaned_html)
        self.assertIn('color: #0066cc', cleaned_html)
        self.assertIn('margin: 0 0 10px 0', cleaned_html)
        self.assertIn('line-height: 1.6', cleaned_html)
    
    def test_outlook_specific_elements_handled(self):
        """Test that Outlook-specific HTML elements are handled properly."""
        outlook_html = """
        <!--[if mso]>
        <table><tr><td>Outlook specific content</td></tr></table>
        <![endif]-->
        <div class="MsoNormal">
            <p class="MsoPlainText">Regular content</p>
        </div>
        """
        
        cleaned_html = self.preview_widget._clean_html_content(outlook_html)
        
        # Verify Outlook conditional comments are removed
        self.assertNotIn('<!--[if mso]>', cleaned_html)
        self.assertNotIn('<![endif]-->', cleaned_html)
        
        # Verify regular content is preserved
        self.assertTrue('<div class="MsoNormal">' in cleaned_html)
        self.assertTrue('<p class="MsoPlainText">' in cleaned_html)
        self.assertIn('Regular content', cleaned_html)
    
    def test_email_message_display_integration(self):
        """Test full email message display with layout preservation."""
        # Create mock email message using the proper structure
        from adelfa.core.email.imap_client import EmailHeader
        
        # Create the EmailHeader object properly
        headers = EmailHeader(
            message_id="test@example.com",
            subject="Test Email with Images",
            from_addr="sender@example.com",
            to_addrs=["recipient@example.com"],
            cc_addrs=[],
            bcc_addrs=[],
            date=Mock()
        )
        headers.date.strftime.return_value = "January 1, 2025 at 12:00 PM"
        
        # Mock the EmailMessage object
        message = Mock()
        message.uid = 123
        message.folder = "INBOX"
        message.headers = headers
        message.html_content = """
        <table width="100%" style="border-collapse: collapse;">
            <tr>
                <td style="padding: 20px;">
                    <h1 style="color: #333;">Welcome!</h1>
                    <img src="https://example.com/logo.jpg" width="200" height="100" alt="Logo">
                    <p style="font-size: 14px; line-height: 1.6;">
                        This is a test email with proper HTML layout.
                    </p>
                </td>
            </tr>
        </table>
        """
        message.text_content = None
        message.attachments = []
        message.size = 1024
        
        # Mock the cache manager
        self.preview_widget.cache_manager.get_image_decision.return_value = None
        self.preview_widget.cache_manager.get_link_decision.return_value = None
        
        # Display the message
        self.preview_widget.show_message(message)
        
        # Verify the message was processed (QWebEngineView loads content internally)
        # We can't easily access the rendered HTML, but we can verify the widget state
        self.assertEqual(self.preview_widget.current_message, message)
        self.assertIsNotNone(self.preview_widget.current_email_hash)
        
        # Test that the HTML cleaning function works correctly with this content
        cleaned_html = self.preview_widget._clean_html_content(message.html_content)
        
        # Verify HTML content structure is preserved
        self.assertIn('<table', cleaned_html)
        self.assertTrue('width: 100%' in cleaned_html or 'width="100%"' in cleaned_html)
        self.assertIn('<h1', cleaned_html)
        self.assertIn('color: #333', cleaned_html)
        self.assertIn('alt="Logo"', cleaned_html)
        self.assertIn('Welcome!', cleaned_html)
        self.assertIn('This is a test email with proper HTML layout.', cleaned_html)
    
    def test_modern_css_properties_preserved(self):
        """Test that all modern CSS properties are preserved with QWebEngineView."""
        html_with_modern_css = """
        <div style="border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); padding: 16px;">
            <button style="border-radius: 6px; background: #007bff; 
                           box-shadow: 0 2px 4px rgba(0,0,0,0.2); transform: translateY(-1px); margin: 8px;">
                Rounded Button
            </button>
            <div style="background: #ff6b6b; border-radius: 8px; padding: 20px; 
                        text-shadow: 1px 1px 2px rgba(0,0,0,0.3); color: white;">
                Styled Box
            </div>
        </div>
        """
        
        cleaned_html = self.preview_widget._clean_html_content(html_with_modern_css)
        
        # Verify that layout-important CSS properties are preserved
        self.assertIn('border-radius: 12px', cleaned_html)
        self.assertIn('border-radius: 6px', cleaned_html)
        self.assertIn('border-radius: 8px', cleaned_html)
        self.assertIn('background: #007bff', cleaned_html)
        self.assertIn('background: #ff6b6b', cleaned_html)
        self.assertIn('padding: 16px', cleaned_html)
        self.assertIn('padding: 20px', cleaned_html)
        self.assertIn('margin: 8px', cleaned_html)
        self.assertIn('color: white', cleaned_html)
        
        # Verify that all modern CSS properties are preserved with QWebEngineView (Chromium engine)
        self.assertIn('box-shadow:', cleaned_html)
        self.assertIn('transform:', cleaned_html)
        self.assertIn('text-shadow:', cleaned_html)
        
        # Verify content structure is maintained
        self.assertIn('Rounded Button', cleaned_html)
        self.assertIn('Styled Box', cleaned_html)
    
    def test_css_button_classes_support(self):
        """Test that CSS button classes are properly supported in the stylesheet."""
        html_with_button_classes = """
        <div class="email-wrapper">
            <a href="#" class="cta-button">Primary CTA</a>
            <button class="btn-secondary">Secondary Button</button>
            <div class="card rounded shadow">
                <p>Card with rounded corners and shadow</p>
            </div>
            <div class="rounded-full bg-primary text-center" style="width: 60px; height: 60px;">
                Circle
            </div>
        </div>
        """
        
        cleaned_html = self.preview_widget._clean_html_content(html_with_button_classes)
        
        # Verify that class names are preserved
        self.assertTrue('class="cta-button"' in cleaned_html)
        self.assertTrue('class="btn-secondary"' in cleaned_html)
        self.assertTrue('class="card rounded shadow"' in cleaned_html)
        self.assertTrue('class="rounded-full bg-primary text-center"' in cleaned_html)
        
        # Verify content is preserved
        self.assertIn('Primary CTA', cleaned_html)
        self.assertIn('Secondary Button', cleaned_html)
        self.assertIn('Card with rounded corners and shadow', cleaned_html)
        self.assertIn('Circle', cleaned_html)
    
    def test_flexbox_and_grid_css_preserved(self):
        """Test that modern layout CSS like flexbox and grid are preserved."""
        html_with_modern_layout = """
        <div style="display: flex; justify-content: center; align-items: center; flex-direction: column;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <div class="flex items-center">Item 1</div>
                <div class="flex items-center">Item 2</div>
            </div>
        </div>
        """
        
        cleaned_html = self.preview_widget._clean_html_content(html_with_modern_layout)
        
        # Verify flexbox properties are preserved
        self.assertIn('display: flex', cleaned_html)
        self.assertIn('justify-content: center', cleaned_html)
        self.assertIn('align-items: center', cleaned_html)
        self.assertIn('flex-direction: column', cleaned_html)
        
        # Verify grid properties are preserved
        self.assertIn('display: grid', cleaned_html)
        self.assertIn('grid-template-columns:', cleaned_html)
        self.assertIn('gap: 16px', cleaned_html)
        
        # Verify class names are preserved
        self.assertTrue('class="flex items-center"' in cleaned_html)
    
    def test_dangerous_css_removed_modern_preserved(self):
        """Test that dangerous CSS is removed while safe CSS is preserved, and unsupported properties are cleaned."""
        dangerous_modern_html = """
        <div style="border-radius: 8px; expression(alert('evil')); color: #333;">
            <button style="background: #007bff; 
                           javascript:alert('hack'); border-radius: 6px; 
                           behavior: url(evil.htc); padding: 12px;">
                Modern Button
            </button>
            <div style="color: #666; vbscript:evil(); opacity: 0.8; 
                        @import url('evil.css'); margin: 8px;">
                Styled Element
            </div>
        </div>
        """
        
        cleaned_html = self.preview_widget._clean_html_content(dangerous_modern_html)
        
        # Verify dangerous CSS is removed
        self.assertNotIn('expression(', cleaned_html)
        self.assertNotIn('javascript:', cleaned_html)
        self.assertNotIn('vbscript:', cleaned_html)
        self.assertNotIn('behavior:', cleaned_html)
        self.assertNotIn('@import', cleaned_html)
        
        # Verify safe CSS is preserved
        self.assertIn('border-radius: 8px', cleaned_html)
        self.assertIn('border-radius: 6px', cleaned_html)
        self.assertIn('background: #007bff', cleaned_html)
        self.assertIn('color: #333', cleaned_html)
        self.assertIn('color: #666', cleaned_html)
        self.assertIn('padding: 12px', cleaned_html)
        self.assertIn('opacity: 0.8', cleaned_html)
        self.assertIn('margin: 8px', cleaned_html)
        
        # Verify content is preserved
        self.assertIn('Modern Button', cleaned_html)
        self.assertIn('Styled Element', cleaned_html)
    
    def test_email_specific_styling_classes(self):
        """Test that email-specific CSS classes work properly."""
        html_with_email_classes = """
        <div class="email-wrapper">
            <div class="email-header">
                <h2>Email Header</h2>
            </div>
            <div class="email-content">
                <div class="gmail_quote">
                    <p>This is a quoted email from Gmail</p>
                </div>
                <div class="AppleMailSignature">
                    <p>Sent from my iPhone</p>
                </div>
            </div>
        </div>
        """
        
        cleaned_html = self.preview_widget._clean_html_content(html_with_email_classes)
        
        # Verify email-specific classes are preserved
        self.assertTrue('class="email-wrapper"' in cleaned_html)
        self.assertTrue('class="email-header"' in cleaned_html)
        self.assertTrue('class="email-content"' in cleaned_html)
        self.assertTrue('class="gmail_quote"' in cleaned_html)
        self.assertTrue('class="AppleMailSignature"' in cleaned_html)
        
        # Verify content is preserved
        self.assertIn('Email Header', cleaned_html)
        self.assertIn('This is a quoted email from Gmail', cleaned_html)
        self.assertIn('Sent from my iPhone', cleaned_html)


if __name__ == '__main__':
    unittest.main() 