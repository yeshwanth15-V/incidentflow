from functools import wraps
from flask import flash, redirect, url_for, abort, request, jsonify
from flask_login import current_user

def admin_required(f):
    """Decorator to restrict route access strictly to Admin users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({"error": "Authentication required"}), 401
            flash("Please sign in with administrator credentials.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if not current_user.is_admin:
            if request.is_json:
                return jsonify({"error": "Admin access required"}), 403
            flash("Access denied. Administrator privileges are required for this action.", "danger")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated_function
