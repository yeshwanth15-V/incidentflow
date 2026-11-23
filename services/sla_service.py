from datetime import datetime, timedelta, timezone
from config import Config

def calculate_due_date(priority: str, start_time: datetime = None) -> datetime:
    """
    Calculates the SLA due date based on incident priority.
    Default SLA windows (configurable via Config.SLA_HOURS):
      - Critical: 4 hours
      - High: 8 hours
      - Medium: 24 hours
      - Low: 48 hours
    """
    if start_time is None:
        start_time = datetime.now(timezone.utc)
    elif start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
        
    hours = Config.SLA_HOURS.get(priority, 24)
    return start_time + timedelta(hours=hours)

def get_sla_metrics(incidents):
    """
    Calculates aggregate SLA compliance metrics for a collection of incidents.
    """
    total = len(incidents)
    if total == 0:
        return {
            "within_sla": 0,
            "approaching": 0,
            "overdue": 0,
            "compliance_rate": 100.0
        }
        
    overdue_count = sum(1 for i in incidents if i.is_overdue)
    approaching_count = sum(1 for i in incidents if i.sla_status == "Approaching")
    within_sla_count = total - overdue_count
    compliance_rate = round((within_sla_count / total) * 100, 1)
    
    return {
        "within_sla": within_sla_count,
        "approaching": approaching_count,
        "overdue": overdue_count,
        "compliance_rate": compliance_rate
    }
