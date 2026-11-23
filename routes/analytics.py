from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
from database import db
from models.incident import Incident
from models.user import User
from services.sla_service import get_sla_metrics

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route("/analytics")
@login_required
def index():
    # ROLE-BASED ANALYTICS SCOPE:
    # Admin sees organization-wide metrics.
    # Support Agent sees ONLY their assigned incidents and their own SLA performance.
    if current_user.is_support_agent:
        scoped_incidents = Incident.query.filter_by(assigned_user_id=current_user.id).all()
    else:
        scoped_incidents = Incident.query.all()

    sla_metrics = get_sla_metrics(scoped_incidents)
    
    # Category Distribution
    categories = sorted(list(set(i.category for i in scoped_incidents if i.category)))
    if not categories:
        categories = ["Software", "Hardware", "Network", "Security", "General"]
    category_data = [sum(1 for i in scoped_incidents if i.category == c) for c in categories]
    
    # Priority Distribution
    priorities = ["Critical", "High", "Medium", "Low"]
    priority_data = [sum(1 for i in scoped_incidents if i.priority == p) for p in priorities]
    
    # Status Distribution
    statuses = ["Open", "In Progress", "Resolved", "Closed"]
    status_data = [sum(1 for i in scoped_incidents if i.status == s) for s in statuses]
    
    # 14-day Trend Data
    now = datetime.now(timezone.utc).date()
    trend_labels = [(now - timedelta(days=d)).strftime("%b %d") for d in range(13, -1, -1)]
    created_trend = []
    resolved_trend = []
    
    for d in range(13, -1, -1):
        target_date = now - timedelta(days=d)
        created_count = sum(
            1 for i in scoped_incidents 
            if i.created_at and i.created_at.date() == target_date
        )
        resolved_count = sum(
            1 for i in scoped_incidents 
            if i.resolved_at and i.resolved_at.date() == target_date
        )
        created_trend.append(created_count)
        resolved_trend.append(resolved_count)
        
    # SLA metrics by priority
    priority_sla = {}
    for p in priorities:
        p_incidents = [i for i in scoped_incidents if i.priority == p]
        priority_sla[p] = get_sla_metrics(p_incidents)
        
    # Performance Stats Breakdown:
    # Admin views performance of all agents.
    # Support Agent views ONLY their own performance row.
    if current_user.is_support_agent:
        users = [current_user]
    else:
        users = User.query.filter_by(is_active_account=True).all()

    team_stats = []
    for u in users:
        u_incidents = [i for i in scoped_incidents if i.assigned_user_id == u.id]
        total_assigned = len(u_incidents)
        active = sum(1 for i in u_incidents if not i.is_resolved_or_closed)
        resolved = sum(1 for i in u_incidents if i.is_resolved_or_closed)
        
        u_resolved = [i for i in u_incidents if i.resolved_at and i.created_at]
        if u_resolved:
            tot_sec = sum(
                (i.resolved_at.replace(tzinfo=None) - i.created_at.replace(tzinfo=None)).total_seconds()
                for i in u_resolved
            )
            avg_h = (tot_sec / len(u_resolved)) / 3600
            avg_str = f"{avg_h:.1f}h"
        else:
            avg_str = "N/A"
            
        team_stats.append({
            "name": u.full_name or u.username,
            "role": u.role,
            "total_assigned": total_assigned,
            "active": active,
            "resolved": resolved,
            "avg_resolution": avg_str
        })
        
    return render_template(
        "analytics/index.html",
        total_incidents=len(scoped_incidents),
        sla_metrics=sla_metrics,
        priority_sla=priority_sla,
        team_stats=team_stats,
        chart_data={
            "priority": {"labels": priorities, "data": priority_data},
            "status": {"labels": statuses, "data": status_data},
            "category": {"labels": categories, "data": category_data},
            "trend": {
                "labels": trend_labels,
                "created": created_trend,
                "resolved": resolved_trend
            }
        }
    )

@analytics_bp.route("/analytics/data")
@login_required
def chart_data_api():
    """Returns JSON payload for real-time chart updates (role-scoped)."""
    if current_user.is_support_agent:
        scoped_incidents = Incident.query.filter_by(assigned_user_id=current_user.id).all()
    else:
        scoped_incidents = Incident.query.all()

    priorities = ["Critical", "High", "Medium", "Low"]
    statuses = ["Open", "In Progress", "Resolved", "Closed"]
    categories = sorted(list(set(i.category for i in scoped_incidents if i.category))) or ["General"]
    
    return jsonify({
        "priority": {"labels": priorities, "data": [sum(1 for i in scoped_incidents if i.priority == p) for p in priorities]},
        "status": {"labels": statuses, "data": [sum(1 for i in scoped_incidents if i.status == s) for s in statuses]},
        "category": {"labels": categories, "data": [sum(1 for i in scoped_incidents if i.category == c) for c in categories]}
    })
