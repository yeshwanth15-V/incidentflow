from datetime import datetime, timezone
from database import db

class IncidentActivity(db.Model):
    __tablename__ = "incident_activity"
    
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incident.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    user_name = db.Column(db.String(100), nullable=False, default="System")
    action = db.Column(db.String(100), nullable=False)  # e.g., 'Created', 'Status Changed', 'Assigned', etc.
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Relationships
    incident = db.relationship("Incident", back_populates="activities")
    actor_user = db.relationship("User", back_populates="activities")
    
    def to_dict(self):
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "action": self.action,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
