# Add this to database.py or create sessions.py

from datetime import datetime, timedelta
import uuid
from typing import Dict, Optional

# In-memory session store (for simple implementation)
# In production, you might use Redis or database
active_sessions: Dict[str, dict] = {}

class UserSession:
    def __init__(self, roll_number: str, name: str):
        self.session_id = str(uuid.uuid4())
        self.roll_number = roll_number
        self.name = name
        self.created_at = datetime.now()
        self.status = "pending_calibration"  # pending_calibration, calibrated, expired
        self.calibration_required = True
        
    def to_dict(self):
        return {
            "session_id": self.session_id,
            "roll_number": self.roll_number, 
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "calibration_required": self.calibration_required
        }

def create_user_session(roll_number: str, name: str, should_calibrate: bool) -> UserSession:
    """Create a new user session"""
    session = UserSession(roll_number, name)
    session.calibration_required = should_calibrate
    active_sessions[session.session_id] = session
    return session

def get_user_session(session_id: str) -> Optional[UserSession]:
    """Get user session by ID"""
    return active_sessions.get(session_id)

def complete_user_session(session_id: str) -> bool:
    """Mark session as complete and commit to permanent records"""
    session = active_sessions.get(session_id)
    if session:
        session.status = "calibrated"
        return True
    return False

def cleanup_expired_sessions():
    """Remove sessions older than 1 hour"""
    cutoff = datetime.now() - timedelta(hours=1)
    expired = [sid for sid, session in active_sessions.items() 
               if session.created_at < cutoff]
    
    for session_id in expired:
        del active_sessions[session_id]
    
    return len(expired)
