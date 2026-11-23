from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = "user"
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="Support Agent")  # 'Admin' or 'Support Agent'
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    assigned_incidents = db.relationship("Incident", back_populates="assignee_user", foreign_keys="Incident.assigned_user_id")
    activities = db.relationship("IncidentActivity", back_populates="actor_user")
    
    @property
    def is_active(self):
        """Override Flask-Login is_active to support account deactivation."""
        return self.is_active_account
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        return self.role == "Admin"
    
    @property
    def is_support_agent(self):
        return self.role == "Support Agent"
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active_account,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
