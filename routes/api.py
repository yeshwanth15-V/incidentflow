from flask import Blueprint, jsonify, request
from flask_login import current_user
from database import db
from models.incident import Incident
from models.user import User
from services.sla_service import calculate_due_date, get_sla_metrics
from services.audit_service import log_activity
from datetime import datetime, timezone

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route("/incidents", methods=["GET"])
def get_all_incidents():
    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")
    
    query = Incident.query
    
    # ROLE ISOLATION: Support Agents can only query their assigned incidents
    if current_user.is_authenticated and current_user.is_support_agent:
        query = query.filter_by(assigned_user_id=current_user.id)
        
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)
        
    incidents = query.order_by(Incident.id.asc()).all()
    return jsonify([i.to_dict() for i in incidents]), 200

@api_bp.route("/incidents/<int:incident_id>", methods=["GET"])
def get_incident(incident_id):
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        return jsonify({"error": "Incident not found", "incident_id": incident_id}), 404

    # ROLE ISOLATION: Support Agents can only access their assigned incidents
    if current_user.is_authenticated and current_user.is_support_agent:
        if incident.assigned_user_id != current_user.id:
            return jsonify({"error": "Access denied: You can only view incidents assigned to you."}), 403

    return jsonify(incident.to_dict()), 200

@api_bp.route("/incidents", methods=["POST"])
def create_incident():
    # ROLE ISOLATION: Support Agents cannot create incidents
    if current_user.is_authenticated and current_user.is_support_agent:
        return jsonify({"error": "Access denied: Support agents cannot create incidents."}), 403

    data = request.get_json() or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    priority = data.get("priority", "Medium")
    category = data.get("category", "General")
    assigned_to = data.get("assigned_to")
    
    if not title or not description:
        return jsonify({"error": "Title and description are required fields."}), 400
        
    valid_priorities = ["Critical", "High", "Medium", "Low"]
    if priority not in valid_priorities:
        return jsonify({"error": f"Invalid priority. Allowed values: {valid_priorities}"}), 400
        
    due_date = calculate_due_date(priority)
    new_incident = Incident(
        title=title,
        description=description,
        priority=priority,
        category=category,
        status="Open",
        assigned_to=assigned_to,
        due_date=due_date,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    if assigned_to:
        user = User.query.filter(
            (User.full_name == assigned_to) | (User.username == assigned_to)
        ).first()
        if user:
            new_incident.assigned_user_id = user.id
            
    db.session.add(new_incident)
    db.session.commit()
    
    log_activity(
        new_incident.id, 
        "Incident Created via API", 
        new_value=f"Title: {new_incident.title} | Priority: {new_incident.priority}"
    )
    
    return jsonify({
        "message": "Incident created successfully!",
        "incident_id": new_incident.id,
        "incident": new_incident.to_dict()
    }), 201

@api_bp.route("/incidents/<int:incident_id>", methods=["PUT"])
def update_incident(incident_id):
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        return jsonify({"error": "Incident not found"}), 404
        
    data = request.get_json() or {}
    
    # ROLE RESTRICTION: Support Agents can ONLY update status on their assigned incidents
    if current_user.is_authenticated and current_user.is_support_agent:
        if incident.assigned_user_id != current_user.id:
            return jsonify({"error": "Access denied: You can only update incidents assigned to you."}), 403
            
        disallowed = [k for k in data.keys() if k not in ("status", "comment")]
        if disallowed:
            return jsonify({"error": f"Access denied: Support agents can only update status. Unauthorized fields: {disallowed}"}), 403

    if "title" in data and (not current_user.is_authenticated or current_user.is_admin):
        incident.title = data["title"].strip()
    if "description" in data and (not current_user.is_authenticated or current_user.is_admin):
        incident.description = data["description"].strip()
    if "priority" in data and (not current_user.is_authenticated or current_user.is_admin):
        incident.priority = data["priority"]
        incident.due_date = calculate_due_date(incident.priority, incident.created_at)
    if "category" in data and (not current_user.is_authenticated or current_user.is_admin):
        incident.category = data["category"]
    if "status" in data:
        incident.status = data["status"]
        if incident.status in ("Resolved", "Closed") and not incident.resolved_at:
            incident.resolved_at = datetime.now(timezone.utc)
        elif incident.status not in ("Resolved", "Closed"):
            incident.resolved_at = None
    if "assigned_to" in data and (not current_user.is_authenticated or current_user.is_admin):
        incident.assigned_to = data["assigned_to"]
        user = User.query.filter(
            (User.full_name == data["assigned_to"]) | (User.username == data["assigned_to"])
        ).first()
        if user:
            incident.assigned_user_id = user.id
            
    incident.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    log_activity(
        incident.id,
        "Incident Updated via API",
        new_value=f"Status: {incident.status}, Priority: {incident.priority}"
    )
    
    return jsonify({
        "message": "Incident updated successfully!",
        "incident": incident.to_dict()
    }), 200

@api_bp.route("/incidents/<int:incident_id>", methods=["DELETE"])
def delete_incident(incident_id):
    # ROLE ISOLATION: Support Agents cannot delete incidents
    if current_user.is_authenticated and not current_user.is_admin:
        return jsonify({"error": "Access denied: Support agents cannot delete incidents."}), 403

    incident = db.session.get(Incident, incident_id)
    if incident is None:
        return jsonify({"error": "Incident not found"}), 404
        
    db.session.delete(incident)
    db.session.commit()
    return jsonify({"message": "Incident deleted successfully!"}), 200

@api_bp.route("/stats", methods=["GET"])
def get_stats():
    # ROLE ISOLATION: Support Agents receive stats for their assigned incidents only
    if current_user.is_authenticated and current_user.is_support_agent:
        incidents = Incident.query.filter_by(assigned_user_id=current_user.id).all()
    else:
        incidents = Incident.query.all()

    sla = get_sla_metrics(incidents)
    return jsonify({
        "total": len(incidents),
        "open": sum(1 for i in incidents if i.status == "Open"),
        "in_progress": sum(1 for i in incidents if i.status == "In Progress"),
        "resolved": sum(1 for i in incidents if i.status in ("Resolved", "Closed")),
        "critical": sum(1 for i in incidents if i.priority == "Critical"),
        "overdue": sum(1 for i in incidents if i.is_overdue),
        "sla_compliance_rate": sla["compliance_rate"]
    }), 200
