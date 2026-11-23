from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from database import db
from models.incident import Incident
from models.user import User
from models.activity import IncidentActivity
from services.sla_service import get_sla_metrics

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def index():
    # ROLE-BASED INCIDENT SCOPE:
    # Admin sees all incidents across the organization.
    # Support Agent sees ONLY incidents assigned to them.
    if current_user.is_support_agent:
        scoped_incidents = Incident.query.filter_by(assigned_user_id=current_user.id).order_by(Incident.created_at.desc()).all()
    else:
        scoped_incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    
    total_incidents = len(scoped_incidents)
    open_count = sum(1 for i in scoped_incidents if i.status == "Open")
    in_progress_count = sum(1 for i in scoped_incidents if i.status == "In Progress")
    resolved_count = sum(1 for i in scoped_incidents if i.status in ("Resolved", "Closed"))
    
    # Critical and High active incidents
    critical_high_count = sum(
        1 for i in scoped_incidents 
        if i.priority in ("Critical", "High") and not i.is_resolved_or_closed
    )
    
    # Overdue incidents
    overdue_count = sum(1 for i in scoped_incidents if i.is_overdue)
    
    # Average Resolution Time calculation (from actual timestamps)
    resolved_incidents = [i for i in scoped_incidents if i.resolved_at and i.created_at]
    if resolved_incidents:
        total_seconds = sum(
            (i.resolved_at.replace(tzinfo=None) - i.created_at.replace(tzinfo=None)).total_seconds()
            for i in resolved_incidents
        )
        avg_seconds = total_seconds / len(resolved_incidents)
        avg_hours = avg_seconds / 3600
        if avg_hours < 1:
            avg_resolution_time = f"{int(avg_seconds // 60)} mins"
        elif avg_hours < 24:
            avg_resolution_time = f"{avg_hours:.1f} hours"
        else:
            avg_days = avg_hours / 24
            avg_resolution_time = f"{avg_days:.1f} days"
    else:
        avg_resolution_time = "N/A"
        
    # Chart Data 1: Priority Breakdown
    priority_labels = ["Critical", "High", "Medium", "Low"]
    priority_counts = [
        sum(1 for i in scoped_incidents if i.priority == p)
        for p in priority_labels
    ]
    
    # Chart Data 2: Status Breakdown
    status_labels = ["Open", "In Progress", "Resolved", "Closed"]
    status_counts = [
        sum(1 for i in scoped_incidents if i.status == s)
        for s in status_labels
    ]
    
    # Chart Data 3: Category Breakdown
    categories = sorted(list(set(i.category for i in scoped_incidents if i.category)))
    if not categories:
        categories = ["Software", "Hardware", "Network", "Security", "General"]
    category_counts = [
        sum(1 for i in scoped_incidents if i.category == c)
        for c in categories
    ]
    
    # Chart Data 4: 7-Day Trend (actual incidents created per day)
    now = datetime.now(timezone.utc).date()
    date_labels = [(now - timedelta(days=d)).strftime("%b %d") for d in range(6, -1, -1)]
    trend_counts = []
    for d in range(6, -1, -1):
        target_date = now - timedelta(days=d)
        cnt = sum(
            1 for i in scoped_incidents 
            if i.created_at and i.created_at.date() == target_date
        )
        trend_counts.append(cnt)
        
    # Chart Data 5: Team Member Workload (Admin only)
    user_names = []
    user_workloads = []
    if current_user.is_admin:
        users = User.query.filter_by(is_active_account=True).all()
        user_names = [u.full_name or u.username for u in users]
        user_workloads = [
            sum(1 for i in scoped_incidents if i.assigned_user_id == u.id and not i.is_resolved_or_closed)
            for u in users
        ]
        unassigned_count = sum(1 for i in scoped_incidents if not i.assigned_user_id and not i.is_resolved_or_closed)
        if unassigned_count > 0 or not user_names:
            user_names.append("Unassigned")
            user_workloads.append(unassigned_count)
        
    # Recent Incidents (Top 6)
    recent_incidents = scoped_incidents[:6]
    
    # Activity History:
    # Admin sees system-wide activities.
    # Support Agent sees ONLY activities on their assigned incidents.
    if current_user.is_support_agent:
        agent_inc_ids = [i.id for i in scoped_incidents]
        if agent_inc_ids:
            recent_activities = IncidentActivity.query.filter(
                IncidentActivity.incident_id.in_(agent_inc_ids)
            ).order_by(IncidentActivity.timestamp.desc()).limit(8).all()
        else:
            recent_activities = []
    else:
        recent_activities = IncidentActivity.query.order_by(IncidentActivity.timestamp.desc()).limit(8).all()
    
    # SLA summary metrics for current scope
    sla_metrics = get_sla_metrics(scoped_incidents)
    
    my_active_count = sum(
        1 for i in scoped_incidents 
        if i.assigned_user_id == current_user.id and not i.is_resolved_or_closed
    )
    
    return render_template(
        "dashboard/index.html",
        total=total_incidents,
        open_count=open_count,
        in_progress_count=in_progress_count,
        resolved_count=resolved_count,
        critical_high_count=critical_high_count,
        overdue_count=overdue_count,
        avg_resolution_time=avg_resolution_time,
        recent_incidents=recent_incidents,
        recent_activities=recent_activities,
        sla_metrics=sla_metrics,
        my_active_count=my_active_count,
        chart_data={
            "priority": {"labels": priority_labels, "data": priority_counts},
            "status": {"labels": status_labels, "data": status_counts},
            "category": {"labels": categories, "data": category_counts},
            "trend": {"labels": date_labels, "data": trend_counts},
            "workload": {"labels": user_names, "data": user_workloads}
        }
    )
