from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime, timezone
from sqlalchemy import or_, desc, asc, case
from database import db
from models.incident import Incident
from models.user import User
from forms.incident_forms import (
    IncidentCreateForm, 
    IncidentEditForm, 
    IncidentStatusUpdateForm,
    CATEGORY_CHOICES,
    PRIORITY_CHOICES,
    STATUS_CHOICES
)
from services.sla_service import calculate_due_date
from services.audit_service import log_activity
from services.email_service import notify_incident_assigned, notify_incident_status_changed
from config import Config
from routes import admin_required

incidents_bp = Blueprint("incidents", __name__)

@incidents_bp.route("/incidents", methods=["GET", "POST"])
@login_required
def list_or_create():
    # Handle POST to /incidents (Creation is strictly Admin-only)
    if request.method == "POST":
        if not current_user.is_admin:
            if request.is_json:
                return jsonify({"error": "Access denied: Support agents cannot create incidents."}), 403
            flash("Access denied: Support agents are not authorized to create incidents.", "danger")
            return redirect(url_for("incidents.list_or_create")), 403
        return create_incident_handler()

    # Query Params for Search, Filter, Sort, Pagination
    search_query = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    category_filter = request.args.get("category", "").strip()
    assignee_filter = request.args.get("assignee", "").strip()
    sort_by = request.args.get("sort", "newest").strip()
    page = request.args.get("page", 1, type=int)
    per_page = Config.ITEMS_PER_PAGE

    query = Incident.query

    # ROLE-BASED DATA ISOLATION: Support Agents ONLY see their assigned incidents
    if current_user.is_support_agent:
        query = query.filter(Incident.assigned_user_id == current_user.id)
    elif assignee_filter:
        # Admin filtering by assignee
        if assignee_filter == "my":
            query = query.filter(Incident.assigned_user_id == current_user.id)
        elif assignee_filter == "unassigned":
            query = query.filter(Incident.assigned_user_id.is_(None))
        elif assignee_filter.isdigit():
            query = query.filter(Incident.assigned_user_id == int(assignee_filter))

    # 1. Search (by ID or Title/Description)
    if search_query:
        clean_id = search_query.upper().replace("INC-", "").lstrip("0")
        if clean_id.isdigit():
            query = query.filter(
                or_(
                    Incident.id == int(clean_id),
                    Incident.title.ilike(f"%{search_query}%"),
                    Incident.description.ilike(f"%{search_query}%")
                )
            )
        else:
            query = query.filter(
                or_(
                    Incident.title.ilike(f"%{search_query}%"),
                    Incident.description.ilike(f"%{search_query}%")
                )
            )

    # 2. Filters
    if status_filter:
        if status_filter == "Active":
            query = query.filter(Incident.status.in_(["Open", "In Progress"]))
        elif status_filter == "Overdue":
            now = datetime.now(timezone.utc)
            query = query.filter(
                Incident.due_date < now,
                Incident.status.notin_(["Resolved", "Closed"])
            )
        else:
            query = query.filter(Incident.status == status_filter)

    if priority_filter:
        query = query.filter(Incident.priority == priority_filter)

    if category_filter:
        query = query.filter(Incident.category == category_filter)

    # 3. Sorting
    if sort_by == "oldest":
        query = query.order_by(asc(Incident.created_at))
    elif sort_by == "priority":
        priority_order = case(
            (Incident.priority == "Critical", 1),
            (Incident.priority == "High", 2),
            (Incident.priority == "Medium", 3),
            (Incident.priority == "Low", 4),
            else_=5
        )
        query = query.order_by(priority_order)
    elif sort_by == "status":
        query = query.order_by(Incident.status)
    elif sort_by == "due_date":
        query = query.order_by(asc(Incident.due_date))
    else:  # newest default
        query = query.order_by(desc(Incident.created_at))

    # If client requests JSON, return filtered incidents as JSON
    if request.is_json or request.headers.get("Accept") == "application/json":
        incidents = query.all()
        return jsonify([i.to_dict() for i in incidents]), 200

    # 4. Server-Side Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    incidents = pagination.items

    # Fetch active team members for admin assignee filter dropdown
    team_members = []
    if current_user.is_admin:
        team_members = User.query.filter_by(is_active_account=True).order_by(User.full_name.asc()).all()

    return render_template(
        "incidents/list.html",
        incidents=incidents,
        pagination=pagination,
        search_query=search_query,
        status_filter=status_filter,
        priority_filter=priority_filter,
        category_filter=category_filter,
        assignee_filter=assignee_filter,
        sort_by=sort_by,
        team_members=team_members,
        priority_choices=[c[0] for c in PRIORITY_CHOICES],
        status_choices=[c[0] for c in STATUS_CHOICES],
        category_choices=[c[0] for c in CATEGORY_CHOICES]
    )


def create_incident_handler():
    """Unified handler for incident creation (Admin-only)."""
    # JSON Request
    if request.is_json:
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        description = data.get("description", "").strip()
        priority = data.get("priority", "Medium")
        category = data.get("category", "General")
        assigned_to_name = data.get("assigned_to", "")
        assigned_user_id = data.get("assigned_user_id")

        if not title or not description:
            return jsonify({"error": "Title and description are required."}), 400

        assigned_user = None
        if assigned_user_id:
            assigned_user = db.session.get(User, int(assigned_user_id))
        elif assigned_to_name:
            assigned_user = User.query.filter(
                (User.full_name == assigned_to_name) | (User.username == assigned_to_name)
            ).first()

        due_date = calculate_due_date(priority)

        new_incident = Incident(
            title=title,
            description=description,
            priority=priority,
            category=category,
            status="Open",
            assigned_to=assigned_to_name or (assigned_user.full_name if assigned_user else None),
            assigned_user_id=assigned_user.id if assigned_user else None,
            due_date=due_date,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.session.add(new_incident)
        db.session.commit()

        log_activity(
            incident_id=new_incident.id,
            action="Incident Created",
            new_value=f"Title: {new_incident.title} | Priority: {new_incident.priority} | SLA: {new_incident.due_date.strftime('%Y-%m-%d %H:%M')}"
        )

        if assigned_user and assigned_user.email:
            notify_incident_assigned(new_incident, assigned_user.email, assigned_user.full_name)

        return jsonify({
            "message": "Incident created successfully!",
            "incident_id": new_incident.id,
            "incident": new_incident.to_dict()
        }), 201

    # Form Submission from Web UI
    form = IncidentCreateForm()
    active_users = User.query.filter_by(is_active_account=True).order_by(User.full_name.asc()).all()
    form.assigned_user_id.choices = [(0, "Unassigned")] + [(u.id, f"{u.full_name} ({u.role})") for u in active_users]

    if form.validate_on_submit():
        user_id = form.assigned_user_id.data if form.assigned_user_id.data != 0 else None
        assigned_user = db.session.get(User, user_id) if user_id else None
        assigned_to_name = assigned_user.full_name if assigned_user else None

        due_date = calculate_due_date(form.priority.data)

        new_incident = Incident(
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            priority=form.priority.data,
            category=form.category.data,
            status="Open",
            assigned_user_id=user_id,
            assigned_to=assigned_to_name,
            due_date=due_date,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.session.add(new_incident)
        db.session.commit()

        log_activity(
            incident_id=new_incident.id,
            action="Incident Created",
            new_value=f"Priority: {new_incident.priority}, Category: {new_incident.category}, SLA: {new_incident.due_date.strftime('%Y-%m-%d %H:%M')}"
        )

        if assigned_user and assigned_user.email:
            notify_incident_assigned(new_incident, assigned_user.email, assigned_user.full_name)

        flash(f"Incident {new_incident.reference_id} created successfully!", "success")
        return redirect(url_for("incidents.view_incident", incident_id=new_incident.id))

    return render_template("incidents/create.html", form=form)


@incidents_bp.route("/incidents/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_incident():
    """Create incident ticket (Admin-only)."""
    form = IncidentCreateForm()
    active_users = User.query.filter_by(is_active_account=True).order_by(User.full_name.asc()).all()
    form.assigned_user_id.choices = [(0, "Unassigned")] + [(u.id, f"{u.full_name} ({u.role})") for u in active_users]

    if form.validate_on_submit():
        user_id = form.assigned_user_id.data if form.assigned_user_id.data != 0 else None
        assigned_user = db.session.get(User, user_id) if user_id else None

        due_date = calculate_due_date(form.priority.data)

        new_incident = Incident(
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            priority=form.priority.data,
            category=form.category.data,
            status="Open",
            assigned_user_id=user_id,
            assigned_to=assigned_user.full_name if assigned_user else None,
            due_date=due_date,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.session.add(new_incident)
        db.session.commit()

        log_activity(
            incident_id=new_incident.id,
            action="Incident Created",
            new_value=f"Priority: {new_incident.priority}, Category: {new_incident.category}"
        )

        if assigned_user and assigned_user.email:
            notify_incident_assigned(new_incident, assigned_user.email, assigned_user.full_name)

        flash(f"Incident {new_incident.reference_id} has been created.", "success")
        return redirect(url_for("incidents.view_incident", incident_id=new_incident.id))

    return render_template("incidents/create.html", form=form)


@incidents_bp.route("/incidents/<int:incident_id>", methods=["GET"])
@login_required
def view_incident(incident_id):
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        if request.is_json:
            return jsonify({"error": "Incident not found"}), 404
        flash(f"Incident #{incident_id} was not found.", "warning")
        return redirect(url_for("incidents.list_or_create"))

    # DATA ISOLATION: Support Agents can only access their assigned incidents
    if not current_user.is_admin and incident.assigned_user_id != current_user.id:
        if request.is_json:
            return jsonify({"error": "Access denied: You can only view incidents assigned to you."}), 403
        flash("Access denied: You are only authorized to view incidents assigned to you.", "danger")
        return redirect(url_for("incidents.list_or_create")), 403

    if request.is_json:
        return jsonify(incident.to_dict()), 200

    # Forms for quick updates on details view
    status_form = IncidentStatusUpdateForm(status=incident.status)
    active_users = []
    if current_user.is_admin:
        active_users = User.query.filter_by(is_active_account=True).order_by(User.full_name.asc()).all()

    return render_template(
        "incidents/detail.html",
        incident=incident,
        status_form=status_form,
        team_members=active_users
    )


@incidents_bp.route("/incidents/<int:incident_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_incident(incident_id):
    """Edit incident ticket details (Admin-only)."""
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        flash(f"Incident #{incident_id} not found.", "warning")
        return redirect(url_for("incidents.list_or_create"))

    form = IncidentEditForm(obj=incident)
    active_users = User.query.filter_by(is_active_account=True).order_by(User.full_name.asc()).all()
    form.assigned_user_id.choices = [(0, "Unassigned")] + [(u.id, f"{u.full_name} ({u.role})") for u in active_users]

    if request.method == "GET":
        form.assigned_user_id.data = incident.assigned_user_id or 0

    if form.validate_on_submit():
        changes = []

        if incident.title != form.title.data.strip():
            changes.append(("Title Updated", incident.title, form.title.data.strip()))
            incident.title = form.title.data.strip()

        if incident.description != form.description.data.strip():
            changes.append(("Description Updated", "Previous description updated", "New description applied"))
            incident.description = form.description.data.strip()

        if incident.category != form.category.data:
            changes.append(("Category Changed", incident.category, form.category.data))
            incident.category = form.category.data

        if incident.priority != form.priority.data:
            old_prio = incident.priority
            new_prio = form.priority.data
            incident.priority = new_prio
            incident.due_date = calculate_due_date(new_prio, incident.created_at)
            changes.append(("Priority Changed", old_prio, f"{new_prio} (SLA recalculated: {incident.due_date.strftime('%Y-%m-%d %H:%M')})"))

        new_status = form.status.data
        if incident.status != new_status:
            old_status = incident.status
            incident.status = new_status
            if new_status in ("Resolved", "Closed") and not incident.resolved_at:
                incident.resolved_at = datetime.now(timezone.utc)
            elif new_status not in ("Resolved", "Closed"):
                incident.resolved_at = None
            changes.append(("Status Changed", old_status, new_status))

        new_assigned_user_id = form.assigned_user_id.data if form.assigned_user_id.data != 0 else None
        if incident.assigned_user_id != new_assigned_user_id:
            old_assignee_name = incident.display_assignee
            new_user = db.session.get(User, new_assigned_user_id) if new_assigned_user_id else None
            new_assignee_name = new_user.full_name if new_user else "Unassigned"
            incident.assigned_user_id = new_assigned_user_id
            incident.assigned_to = new_assignee_name if new_user else None
            changes.append(("Assignee Changed", old_assignee_name, new_assignee_name))

            if new_user and new_user.email:
                notify_incident_assigned(incident, new_user.email, new_user.full_name)

        incident.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Log all atomic changes
        for action, old_v, new_v in changes:
            log_activity(incident.id, action, old_value=old_v, new_value=new_v)

        flash(f"Incident {incident.reference_id} was successfully updated.", "success")
        return redirect(url_for("incidents.view_incident", incident_id=incident.id))

    return render_template("incidents/edit.html", form=form, incident=incident)


@incidents_bp.route("/incidents/<int:incident_id>/status", methods=["POST"])
@login_required
def update_status(incident_id):
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("incidents.list_or_create"))

    # PERMISSION CHECK: Support Agents can only update status of their assigned incidents
    if not current_user.is_admin and incident.assigned_user_id != current_user.id:
        flash("Access denied: You are not authorized to update this incident's status.", "danger")
        return redirect(url_for("incidents.list_or_create")), 403

    new_status = request.form.get("status")
    comment = request.form.get("comment", "").strip()

    valid_statuses = [c[0] for c in STATUS_CHOICES]
    if new_status not in valid_statuses:
        flash("Invalid status specified.", "danger")
        return redirect(url_for("incidents.view_incident", incident_id=incident_id))

    old_status = incident.status
    if old_status != new_status:
        incident.status = new_status
        if new_status in ("Resolved", "Closed") and not incident.resolved_at:
            incident.resolved_at = datetime.now(timezone.utc)
        elif new_status not in ("Resolved", "Closed"):
            incident.resolved_at = None

        incident.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        action_desc = "Status Changed"
        if new_status == "Resolved":
            action_desc = "Incident Resolved"
        elif new_status == "Closed":
            action_desc = "Incident Closed"

        note = f"{old_status} -> {new_status}"
        if comment:
            note += f" (Note: {comment})"

        log_activity(incident.id, action_desc, old_value=old_status, new_value=note)

        # Notify assignee or admin
        if incident.assignee_user and incident.assignee_user.email and incident.assigned_user_id != current_user.id:
            notify_incident_status_changed(incident, old_status, new_status, incident.assignee_user.email)

        flash(f"Status updated to '{new_status}' successfully.", "success")
    else:
        flash("Status is unchanged.", "info")

    return redirect(url_for("incidents.view_incident", incident_id=incident_id))


@incidents_bp.route("/incidents/<int:incident_id>/assign", methods=["POST"])
@login_required
@admin_required
def assign_incident(incident_id):
    """Assign or reassign incident (Admin-only)."""
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("incidents.list_or_create"))

    target_user_id = request.form.get("assigned_user_id", type=int)
    old_assignee = incident.display_assignee

    if target_user_id == 0 or target_user_id is None:
        incident.assigned_user_id = None
        incident.assigned_to = None
        new_assignee = "Unassigned"
    else:
        user = db.session.get(User, target_user_id)
        if not user or not user.is_active:
            flash("Selected team member is invalid or inactive.", "danger")
            return redirect(url_for("incidents.view_incident", incident_id=incident_id))
        incident.assigned_user_id = user.id
        incident.assigned_to = user.full_name
        new_assignee = user.full_name

        if user.email:
            notify_incident_assigned(incident, user.email, user.full_name)

    incident.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_activity(incident.id, "Reassigned", old_value=old_assignee, new_value=new_assignee)
    flash(f"Incident reassigned to {new_assignee}.", "success")
    return redirect(url_for("incidents.view_incident", incident_id=incident_id))


@incidents_bp.route("/incidents/<int:incident_id>", methods=["PUT"])
def api_update_incident(incident_id):
    """Preserves PUT /incidents/<id> endpoint with role enforcement."""
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        return jsonify({"message": "Incident not found"}), 404

    data = request.get_json() or {}

    # If authenticated as Support Agent, enforce that they only touch their own incident and only update status
    if current_user.is_authenticated and current_user.is_support_agent:
        if incident.assigned_user_id != current_user.id:
            return jsonify({"error": "Access denied: You can only update incidents assigned to you."}), 403

        # Check for unauthorized field updates
        disallowed = [k for k in data.keys() if k not in ("status", "comment")]
        if disallowed:
            return jsonify({"error": f"Access denied: Support agents can only update status. Unauthorized fields: {disallowed}"}), 403

    old_status = incident.status

    if "title" in data and (not current_user.is_authenticated or current_user.is_admin):
        incident.title = data["title"]
    if "description" in data and (not current_user.is_authenticated or current_user.is_admin):
        incident.description = data["description"]
    if "priority" in data and (not current_user.is_authenticated or current_user.is_admin):
        incident.priority = data["priority"]
        incident.due_date = calculate_due_date(incident.priority, incident.created_at)
    if "status" in data:
        incident.status = data["status"]
        if incident.status in ("Resolved", "Closed") and not incident.resolved_at:
            incident.resolved_at = datetime.now(timezone.utc)
        elif incident.status not in ("Resolved", "Closed"):
            incident.resolved_at = None
    if "assigned_to" in data and (not current_user.is_authenticated or current_user.is_admin):
        incident.assigned_to = data["assigned_to"]
        matched_user = User.query.filter(
            (User.full_name == data["assigned_to"]) | (User.username == data["assigned_to"])
        ).first()
        if matched_user:
            incident.assigned_user_id = matched_user.id

    incident.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_activity(
        incident.id, 
        "Incident Updated via API", 
        old_value=old_status, 
        new_value=f"Status: {incident.status}, Priority: {incident.priority}"
    )

    return jsonify({"message": "Incident updated successfully!", "incident": incident.to_dict()}), 200


@incidents_bp.route("/incidents/<int:incident_id>", methods=["DELETE"])
def api_delete_incident(incident_id):
    """Preserves DELETE /incidents/<id> endpoint (Admin-only)."""
    if current_user.is_authenticated and not current_user.is_admin:
        return jsonify({"error": "Access denied: Support agents cannot delete incidents."}), 403

    incident = db.session.get(Incident, incident_id)
    if incident is None:
        return jsonify({"message": "Incident not found"}), 404

    ref = incident.reference_id
    db.session.delete(incident)
    db.session.commit()

    return jsonify({"message": "Incident deleted successfully!", "reference_id": ref}), 200


@incidents_bp.route("/incidents/<int:incident_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_incident(incident_id):
    """Web UI delete handler (Admin-only)."""
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("incidents.list_or_create"))

    ref = incident.reference_id
    title = incident.title
    db.session.delete(incident)
    db.session.commit()

    flash(f"Incident {ref} ('{title}') was permanently deleted.", "info")
    return redirect(url_for("incidents.list_or_create"))
