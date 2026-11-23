import logging
from datetime import datetime, timezone
from flask_login import current_user
from database import db
from models.activity import IncidentActivity

logger = logging.getLogger(__name__)

def log_activity(incident_id: int, action: str, old_value=None, new_value=None, user_id=None, user_name=None):
    """
    Persistently records an incident audit trail entry.
    Automatically captures current authenticated user or system context.
    """
    try:
        # Resolve actor identity
        if user_id is None and current_user and current_user.is_authenticated:
            user_id = current_user.id
            user_name = current_user.full_name or current_user.username
        elif user_name is None:
            user_name = "System"
            
        activity = IncidentActivity(
            incident_id=incident_id,
            user_id=user_id,
            user_name=user_name,
            action=action,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(activity)
        db.session.commit()
        return activity
    except Exception as e:
        logger.error(f"[AuditLog] Failed to log activity for Incident #{incident_id}: {e}")
        db.session.rollback()
        return None
