from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from models.user import User
from forms.auth_forms import LoginForm
from services.audit_service import log_activity

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
        
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.query.filter(
            (User.username == username) | (User.email == username.lower())
        ).first()
        
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password. Please check your credentials.", "danger")
            return render_template("auth/login.html", form=form)
            
        if not user.is_active:
            flash("This account is currently deactivated. Please contact an administrator.", "warning")
            return render_template("auth/login.html", form=form)
            
        login_user(user, remember=form.remember_me.data)
        flash(f"Welcome back, {user.full_name}!", "success")
        
        next_page = request.args.get("next")
        if not next_page or urlparse(next_page).netloc != "":
            next_page = url_for("dashboard.index")
        return redirect(next_page)
        
    return render_template("auth/login.html", form=form)

@auth_bp.route("/logout")
@login_required
def logout():
    user_name = current_user.full_name
    logout_user()
    flash(f"You have been successfully logged out, {user_name}.", "info")
    return redirect(url_for("auth.login"))
