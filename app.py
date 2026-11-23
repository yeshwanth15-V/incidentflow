import os
import click
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify
from config import Config
from database import db, login_manager, csrf
from migrate_db import run_migrations

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Exempt REST API blueprint from CSRF for external programmatic clients
    from routes.api import api_bp
    csrf.exempt(api_bp)

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.incidents import incidents_bp
    from routes.team import team_bp
    from routes.analytics import analytics_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(api_bp)

    # Template Context Processors & Filters
    @app.context_processor
    def inject_global_template_vars():
        return {
            "current_year": datetime.now(timezone.utc).year,
            "app_name": "IncidentFlow"
        }

    @app.template_filter("datetime_format")
    def format_datetime(value, format="%b %d, %Y %H:%M"):
        if value is None:
            return "N/A"
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except Exception:
                return value
        return value.strftime(format)

    @app.template_filter("time_ago")
    def time_ago_filter(value):
        if not value:
            return "N/A"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        val = value.replace(tzinfo=None) if value.tzinfo else value
        diff = now - val
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            m = seconds // 60
            return f"{m}m ago"
        elif seconds < 86400:
            h = seconds // 3600
            return f"{h}h ago"
        else:
            d = seconds // 86400
            return f"{d}d ago"

    # Custom Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        if request.is_json:
            return jsonify({"error": "Resource not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.is_json:
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    # Ensure database schema is up-to-date safely
    with app.app_context():
        # Import models so SQLAlchemy creates tables
        import models
        run_migrations()
        db.create_all()

    # CLI Command: create-admin
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True, help="Admin username")
    @click.option("--email", prompt=True, help="Admin email address")
    @click.option("--fullname", prompt=True, default="System Administrator", help="Admin display name")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Admin password")
    def create_admin(username, email, fullname, password):
        """Creates the initial Administrator account securely."""
        from models.user import User
        with app.app_context():
            user = User.query.filter((User.username == username) | (User.email == email.lower())).first()
            if user:
                click.secho(f"Error: User with username '{username}' or email '{email}' already exists.", fg="red")
                return

            admin = User(
                username=username.strip(),
                email=email.strip().lower(),
                full_name=fullname.strip(),
                role="Admin",
                is_active_account=True
            )
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            click.secho(f"Success! Administrator account '{admin.username}' created successfully.", fg="green")

    # CLI Command: seed-demo
    @app.cli.command("seed-demo")
    def seed_demo():
        """Seeds realistic demonstration incidents and team members if database is empty."""
        from models.user import User
        from models.incident import Incident
        from services.sla_service import calculate_due_date
        from services.audit_service import log_activity
        from datetime import timedelta

        with app.app_context():
            if Incident.query.count() > 0:
                click.secho("Database already contains incidents. Skipping demo seed to protect existing data.", fg="yellow")
                return

            click.echo("Seeding realistic IT operations demo data...")

            # Create default agents if none exist
            agent1 = User.query.filter_by(username="sarah.ops").first()
            if not agent1:
                agent1 = User(
                    username="sarah.ops",
                    email="sarah.dev@incidentflow.com",
                    full_name="Sarah Jenkins",
                    role="Support Agent",
                    is_active_account=True
                )
                agent1.set_password("AgentPass123!")
                db.session.add(agent1)

            agent2 = User.query.filter_by(username="alex.net").first()
            if not agent2:
                agent2 = User(
                    username="alex.net",
                    email="alex.net@incidentflow.com",
                    full_name="Alex Rivera",
                    role="Support Agent",
                    is_active_account=True
                )
                agent2.set_password("AgentPass123!")
                db.session.add(agent2)

            db.session.commit()

            demo_incidents = [
                {
                    "title": "Production API Gateway 504 Gateway Timeout Spikes",
                    "description": "Upstream microservices latency causing edge gateway connection drops on US-East region. Multiple client timeout reports received.",
                    "priority": "Critical",
                    "status": "In Progress",
                    "category": "Infrastructure",
                    "assigned_user_id": agent1.id,
                    "hours_ago": 2
                },
                {
                    "title": "Primary Database Read Replica Replication Lag",
                    "description": "PostgreSQL read replica lag exceeded 450 seconds. Analytics dashboard queries experiencing delayed data synchronization.",
                    "priority": "High",
                    "status": "Open",
                    "category": "Database",
                    "assigned_user_id": agent2.id,
                    "hours_ago": 4
                },
                {
                    "title": "Corporate VPN LDAP Authentication Intermittent Failures",
                    "description": "Remote staff in London office reporting authentication timeout errors when connecting via OpenVPN gateway.",
                    "priority": "Medium",
                    "status": "In Progress",
                    "category": "Network",
                    "assigned_user_id": agent1.id,
                    "hours_ago": 18
                },
                {
                    "title": "Internal Payment Service Webhook Retry Queue Backlog",
                    "description": "Partner webhook responses returning HTTP 429 rate limit causing exponential retry queue accumulation.",
                    "priority": "Critical",
                    "status": "Resolved",
                    "category": "Software",
                    "assigned_user_id": agent1.id,
                    "hours_ago": 30,
                    "resolved_hours_ago": 5
                },
                {
                    "title": "SSL Certificate Expiration Notice for staging.internal",
                    "description": "Let's Encrypt automated certbot renewal failed due to DNS challenge TXT record propagation timeout.",
                    "priority": "Low",
                    "status": "Resolved",
                    "category": "Security",
                    "assigned_user_id": agent2.id,
                    "hours_ago": 48,
                    "resolved_hours_ago": 20
                },
                {
                    "title": "Office Floor 3 Wi-Fi Access Point Firmware Flapping",
                    "description": "Meraki access point AP-3B rebooting cyclically every 45 minutes after overnight automated patch.",
                    "priority": "Medium",
                    "status": "Open",
                    "category": "Hardware",
                    "assigned_user_id": None,
                    "hours_ago": 5
                }
            ]

            now = datetime.now(timezone.utc)
            for item in demo_incidents:
                created = now - timedelta(hours=item["hours_ago"])
                due = calculate_due_date(item["priority"], created)
                resolved = (now - timedelta(hours=item["resolved_hours_ago"])) if "resolved_hours_ago" in item else None

                u = db.session.get(User, item["assigned_user_id"]) if item["assigned_user_id"] else None

                inc = Incident(
                    title=item["title"],
                    description=item["description"],
                    priority=item["priority"],
                    status=item["status"],
                    category=item["category"],
                    assigned_user_id=item["assigned_user_id"],
                    assigned_to=u.full_name if u else None,
                    created_at=created,
                    updated_at=created,
                    due_date=due,
                    resolved_at=resolved
                )
                db.session.add(inc)
                db.session.commit()

                log_activity(
                    inc.id, 
                    "Incident Created", 
                    new_value=f"Priority: {inc.priority}, Category: {inc.category}",
                    user_name="Seed Script"
                )

                if inc.status in ("In Progress", "Resolved"):
                    log_activity(
                        inc.id,
                        "Status Changed",
                        old_value="Open",
                        new_value=inc.status,
                        user_name="Seed Script"
                    )

            click.secho(f"Successfully seeded {len(demo_incidents)} realistic incidents and 2 support agents!", fg="green")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
