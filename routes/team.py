from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from database import db
from models.user import User
from models.incident import Incident
from forms.auth_forms import CreateUserForm, EditUserForm
from routes import admin_required
from services.audit_service import log_activity

team_bp = Blueprint("team", __name__)

@team_bp.route("/team")
@login_required
@admin_required
def index():
    users = User.query.order_by(User.role.asc(), User.full_name.asc()).all()
    
    # Calculate real workload metrics for each team member
    team_data = []
    for user in users:
        assigned_count = Incident.query.filter_by(assigned_user_id=user.id).count()
        active_workload = Incident.query.filter(
            Incident.assigned_user_id == user.id,
            Incident.status.in_(["Open", "In Progress"])
        ).count()
        resolved_count = Incident.query.filter(
            Incident.assigned_user_id == user.id,
            Incident.status.in_(["Resolved", "Closed"])
        ).count()
        overdue_count = sum(
            1 for inc in user.assigned_incidents 
            if inc.is_overdue
        )
        
        team_data.append({
            "user": user,
            "assigned_count": assigned_count,
            "active_workload": active_workload,
            "resolved_count": resolved_count,
            "overdue_count": overdue_count
        })
        
    return render_template("team/index.html", team_data=team_data)

@team_bp.route("/team/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_member():
    form = CreateUserForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            role=form.role.data,
            is_active_account=True
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash(f"Team member '{user.full_name}' ({user.role}) has been added.", "success")
        return redirect(url_for("team.index"))
        
    return render_template("team/create.html", form=form)

@team_bp.route("/team/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_member(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        flash("Team member not found.", "warning")
        return redirect(url_for("team.index"))
        
    form = EditUserForm(original_user=user, obj=user)
    if form.validate_on_submit():
        user.full_name = form.full_name.data.strip()
        user.email = form.email.data.strip().lower()
        user.role = form.role.data
        user.is_active_account = form.is_active_account.data
        
        if form.new_password.data:
            user.set_password(form.new_password.data)
            
        db.session.commit()
        flash(f"Team member '{user.full_name}' was successfully updated.", "success")
        return redirect(url_for("team.index"))
        
    return render_template("team/edit.html", form=form, user=user)

@team_bp.route("/team/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@admin_required
def toggle_status(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        flash("Team member not found.", "warning")
        return redirect(url_for("team.index"))
        
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("team.index"))
        
    user.is_active_account = not user.is_active_account
    db.session.commit()
    
    state = "activated" if user.is_active_account else "deactivated"
    flash(f"Team member '{user.full_name}' has been {state}.", "info")
    return redirect(url_for("team.index"))
