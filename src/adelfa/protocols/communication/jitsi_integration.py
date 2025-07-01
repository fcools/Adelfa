"""
Jitsi Meet integration for Adelfa PIM suite.

Provides video conferencing capabilities through Jitsi Meet,
including meeting creation, calendar integration, and contact calling.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json
from PyQt6.QtCore import QObject, pyqtSignal, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QLabel


class JitsiMeetingManager(QObject):
    """
    Manager for Jitsi Meet video conferencing integration.
    
    Handles meeting creation, URL generation, and calendar integration.
    """
    
    # Signals
    meeting_started = pyqtSignal(str)  # meeting_id
    meeting_ended = pyqtSignal(str)    # meeting_id
    participant_joined = pyqtSignal(str, str)  # meeting_id, participant_name
    participant_left = pyqtSignal(str, str)    # meeting_id, participant_name
    
    def __init__(self, jitsi_server: str = "https://meet.jit.si", parent: Optional[QObject] = None):
        """
        Initialize Jitsi Meet manager.
        
        Args:
            jitsi_server: Jitsi Meet server URL (default: public server)
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.jitsi_server = jitsi_server.rstrip('/')
        self.active_meetings: Dict[str, Dict[str, Any]] = {}
    
    def create_meeting(self, 
                      meeting_name: Optional[str] = None,
                      password: Optional[str] = None,
                      moderator_password: Optional[str] = None,
                      start_time: Optional[datetime] = None) -> Dict[str, str]:
        """
        Create a new Jitsi Meet meeting.
        
        Args:
            meeting_name: Optional custom meeting name
            password: Optional meeting password
            moderator_password: Optional moderator password
            start_time: Scheduled start time
        
        Returns:
            Dict containing meeting details including URL, room name, etc.
        """
        # Generate unique room name
        if not meeting_name:
            meeting_name = f"adelfa-meeting-{str(uuid.uuid4())[:8]}"
        
        # Sanitize meeting name for URL
        room_name = meeting_name.replace(' ', '-').lower()
        room_name = ''.join(c for c in room_name if c.isalnum() or c in '-_')
        
        # Construct meeting URL
        meeting_url = f"{self.jitsi_server}/{room_name}"
        
        # Add URL parameters for configuration
        url_params = []
        if password:
            url_params.append(f"password={password}")
        
        if url_params:
            meeting_url += "?" + "&".join(url_params)
        
        meeting_info = {
            'meeting_id': str(uuid.uuid4()),
            'room_name': room_name,
            'meeting_name': meeting_name,
            'meeting_url': meeting_url,
            'password': password,
            'moderator_password': moderator_password,
            'start_time': start_time.isoformat() if start_time else None,
            'created_at': datetime.now().isoformat(),
            'status': 'scheduled'
        }
        
        self.active_meetings[meeting_info['meeting_id']] = meeting_info
        return meeting_info
    
    def get_meeting_url_for_contact(self, contact_email: str) -> str:
        """
        Generate a direct meeting URL for calling a specific contact.
        
        Args:
            contact_email: Email address of the contact to call
        
        Returns:
            Jitsi Meet URL for the call
        """
        # Create a room name based on sorted email addresses for consistency
        room_name = f"adelfa-call-{hash(contact_email) % 100000}"
        return f"{self.jitsi_server}/{room_name}"
    
    def get_calendar_meeting_url(self, event_id: str, event_title: str) -> str:
        """
        Generate a meeting URL for a calendar event.
        
        Args:
            event_id: Calendar event ID
            event_title: Event title
        
        Returns:
            Jitsi Meet URL for the calendar event
        """
        # Create consistent room name from event details
        sanitized_title = ''.join(c for c in event_title if c.isalnum() or c in '-_').lower()
        room_name = f"adelfa-event-{event_id}-{sanitized_title}"[:50]  # Limit length
        return f"{self.jitsi_server}/{room_name}"


class JitsiMeetWidget(QWidget):
    """
    Qt widget for embedding Jitsi Meet video conferencing.
    
    Provides a complete video conferencing interface within the application.
    """
    
    def __init__(self, meeting_url: str, parent: Optional[QWidget] = None):
        """
        Initialize Jitsi Meet widget.
        
        Args:
            meeting_url: URL of the Jitsi Meet room
            parent: Parent widget
        """
        super().__init__(parent)
        self.meeting_url = meeting_url
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        
        # Header with meeting info
        header_layout = QHBoxLayout()
        
        meeting_label = QLabel("Video Meeting")
        meeting_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(meeting_label)
        
        header_layout.addStretch()
        
        # Control buttons
        self.mute_button = QPushButton("Mute")
        self.mute_button.setCheckable(True)
        header_layout.addWidget(self.mute_button)
        
        self.video_button = QPushButton("Stop Video")
        self.video_button.setCheckable(True)
        header_layout.addWidget(self.video_button)
        
        self.leave_button = QPushButton("Leave Meeting")
        self.leave_button.clicked.connect(self.leave_meeting)
        header_layout.addWidget(self.leave_button)
        
        layout.addLayout(header_layout)
        
        # Web view for Jitsi Meet
        self.web_view = QWebEngineView()
        
        # Configure Jitsi Meet with custom parameters
        jitsi_config = {
            'startWithAudioMuted': False,
            'startWithVideoMuted': False,
            'requireDisplayName': True,
            'enableWelcomePage': False,
            'prejoinPageEnabled': False,
            'disableThirdPartyRequests': True,
        }
        
        # Construct URL with configuration
        config_js = json.dumps(jitsi_config)
        full_url = f"{self.meeting_url}#config.{config_js}"
        
        self.web_view.load(QUrl(full_url))
        layout.addWidget(self.web_view)
    
    def leave_meeting(self) -> None:
        """Leave the current meeting."""
        # Execute JavaScript to leave the meeting gracefully
        self.web_view.page().runJavaScript("APP.conference.hangup();")
        self.close()
    
    def mute_audio(self, muted: bool) -> None:
        """
        Mute or unmute audio.
        
        Args:
            muted: True to mute, False to unmute
        """
        js_command = f"APP.conference.toggleAudioMuted({str(muted).lower()});"
        self.web_view.page().runJavaScript(js_command)
    
    def mute_video(self, muted: bool) -> None:
        """
        Mute or unmute video.
        
        Args:
            muted: True to mute video, False to unmute
        """
        js_command = f"APP.conference.toggleVideoMuted({str(muted).lower()});"
        self.web_view.page().runJavaScript(js_command)


class ContactVideoCallDialog(QWidget):
    """
    Dialog for initiating video calls with contacts.
    """
    
    def __init__(self, contact_name: str, contact_email: str, parent: Optional[QWidget] = None):
        """
        Initialize contact video call dialog.
        
        Args:
            contact_name: Name of the contact to call
            contact_email: Email of the contact to call
            parent: Parent widget
        """
        super().__init__(parent)
        self.contact_name = contact_name
        self.contact_email = contact_email
        self.jitsi_manager = JitsiMeetingManager()
        
        self.setWindowTitle(f"Video Call - {contact_name}")
        self.setMinimumSize(800, 600)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Call information
        info_label = QLabel(f"Starting video call with {self.contact_name}")
        info_label.setStyleSheet("font-size: 16px; margin: 10px;")
        layout.addWidget(info_label)
        
        # Generate meeting URL for this contact
        meeting_url = self.jitsi_manager.get_meeting_url_for_contact(self.contact_email)
        
        # Embed Jitsi Meet widget
        self.jitsi_widget = JitsiMeetWidget(meeting_url)
        layout.addWidget(self.jitsi_widget)
    
    def send_meeting_invite(self) -> None:
        """
        Send meeting invitation to the contact via email.
        
        This would integrate with the email module to send an invitation.
        """
        # TODO: Integrate with email module
        meeting_url = self.jitsi_manager.get_meeting_url_for_contact(self.contact_email)
        
        email_subject = f"Video Call Invitation from Adelfa"
        email_body = f"""
        You're invited to a video call!
        
        Meeting Link: {meeting_url}
        
        Join the meeting by clicking the link above or copying it to your browser.
        
        Best regards,
        Adelfa PIM Suite
        """
        
        # This would trigger the email composition window
        # self.parent().compose_email(
        #     to=self.contact_email,
        #     subject=email_subject,
        #     body=email_body
        # )


# Integration helper functions for calendar and contacts

def add_jitsi_to_calendar_event(event_id: str, event_title: str) -> str:
    """
    Add Jitsi Meet link to a calendar event.
    
    Args:
        event_id: Calendar event ID
        event_title: Event title
    
    Returns:
        Generated Jitsi Meet URL
    """
    jitsi_manager = JitsiMeetingManager()
    return jitsi_manager.get_calendar_meeting_url(event_id, event_title)


def initiate_contact_video_call(contact_email: str, contact_name: str) -> ContactVideoCallDialog:
    """
    Initiate a video call with a contact.
    
    Args:
        contact_email: Email of the contact
        contact_name: Name of the contact
    
    Returns:
        Video call dialog widget
    """
    return ContactVideoCallDialog(contact_name, contact_email) 