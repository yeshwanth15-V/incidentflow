import os
from datetime import timedelta

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "incidentflow-dev-secret-key-change-in-prod-898069af")
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", 
        "sqlite:///incidents.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session security
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # WTForms CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # SLA Configuration (in hours per priority)
    # Can be overridden via environment variables
    SLA_HOURS = {
        "Critical": int(os.environ.get("SLA_HOURS_CRITICAL", 4)),
        "High": int(os.environ.get("SLA_HOURS_HIGH", 8)),
        "Medium": int(os.environ.get("SLA_HOURS_MEDIUM", 24)),
        "Low": int(os.environ.get("SLA_HOURS_LOW", 48)),
    }
    
    # SLA Approaching Threshold (in minutes) - warning badge shown if remaining <= this
    SLA_APPROACHING_THRESHOLD_MINUTES = int(os.environ.get("SLA_APPROACHING_THRESHOLD_MINUTES", 120))
    
    # Pagination
    ITEMS_PER_PAGE = int(os.environ.get("ITEMS_PER_PAGE", 10))
    
    # SMTP / Email Configuration
    SMTP_ENABLED = os.environ.get("SMTP_ENABLED", "false").lower() in ("true", "1", "yes")
    SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 1025))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "false").lower() in ("true", "1", "yes")
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")
    SMTP_FROM = os.environ.get("SMTP_FROM", "notifications@incidentflow.local")
