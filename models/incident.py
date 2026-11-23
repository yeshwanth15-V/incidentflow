from datetime import datetime, timezone
from database import db

class Incident(db.Model):
    __tablename__ = "incident"
    
    # Preserved original columns
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), nullable=False)  # Critical, High, Medium, Low
    status = db.Column(db.String(20), default="Open", nullable=False)  # Open, In Progress, Resolved, Closed
    assigned_to = db.Column(db.String(100), nullable=True)  # Name / Email string for legacy compatibility
    
    # Extended columns
    category = db.Column(db.String(50), default="General", nullable=False)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)  # SLA deadline
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    assignee_user = db.relationship("User", back_populates="assigned_incidents", foreign_keys=[assigned_user_id])
    activities = db.relationship(
        "IncidentActivity", 
        back_populates="incident", 
        cascade="all, delete-orphan", 
        order_by="desc(IncidentActivity.timestamp)"
    )
    
    @property
    def reference_id(self):
        """Format incident ID as INC-XXXX."""
        return f"INC-{self.id:04d}"
    
    @property
    def display_assignee(self):
        """Return display name of assigned team member."""
        if self.assignee_user:
            return self.assignee_user.full_name or self.assignee_user.username
        if self.assigned_to:
            return self.assigned_to
        return "Unassigned"
    
    @property
    def is_resolved_or_closed(self):
        return self.status in ("Resolved", "Closed")
    
    @property
    def is_overdue(self):
        """Check if SLA deadline has passed."""
        if not self.due_date:
            return False
        if self.is_resolved_or_closed:
            if self.resolved_at:
                # Normalizing timezone for comparison
                res_time = self.resolved_at.replace(tzinfo=None) if self.resolved_at.tzinfo else self.resolved_at
                due_time = self.due_date.replace(tzinfo=None) if self.due_date.tzinfo else self.due_date
                return res_time > due_time
            return False
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        due = self.due_date.replace(tzinfo=None) if self.due_date.tzinfo else self.due_date
        return now > due

    @property
    def sla_status(self):
        """Calculate high-level SLA status."""
        if not self.due_date:
            return "No SLA"
        
        due = self.due_date.replace(tzinfo=None) if self.due_date.tzinfo else self.due_date
        
        if self.is_resolved_or_closed:
            if self.resolved_at:
                res = self.resolved_at.replace(tzinfo=None) if self.resolved_at.tzinfo else self.resolved_at
                return "Resolved Late" if res > due else "Resolved On Time"
            return "Resolved"
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        diff_seconds = (due - now).total_seconds()
        
        if diff_seconds < 0:
            return "Overdue"
        elif diff_seconds <= 2 * 3600:  # <= 2 hours remaining
            return "Approaching"
        return "Within SLA"
    
    @property
    def sla_time_remaining(self):
        """Return human-readable SLA remaining or overdue string."""
        if not self.due_date:
            return "N/A"
        
        due = self.due_date.replace(tzinfo=None) if self.due_date.tzinfo else self.due_date
        ref_time = datetime.now(timezone.utc).replace(tzinfo=None)
        
        if self.is_resolved_or_closed and self.resolved_at:
            ref_time = self.resolved_at.replace(tzinfo=None) if self.resolved_at.tzinfo else self.resolved_at
            
        diff = due - ref_time
        total_seconds = int(diff.total_seconds())
        
        if total_seconds < 0:
            abs_seconds = abs(total_seconds)
            hours, remainder = divmod(abs_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            if hours > 24:
                days = hours // 24
                return f"Overdue by {days}d {hours % 24}h"
            elif hours > 0:
                return f"Overdue by {hours}h {minutes}m"
            else:
                return f"Overdue by {minutes}m"
        else:
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            if hours > 24:
                days = hours // 24
                return f"{days}d {hours % 24}h remaining"
            elif hours > 0:
                return f"{hours}h {minutes}m remaining"
            else:
                return f"{minutes}m remaining"
    
    def to_dict(self):
        return {
            "id": self.id,
            "reference_id": self.reference_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "category": self.category,
            "assigned_to": self.display_assignee,
            "assigned_user_id": self.assigned_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "is_overdue": self.is_overdue,
            "sla_status": self.sla_status,
            "sla_time_remaining": self.sla_time_remaining
        }
