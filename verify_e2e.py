import os
import re
from app import app
from database import db
from models.user import User
from models.incident import Incident

def extract_csrf_token(html):
    """Extract CSRF token from form hidden input or meta tag."""
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if not match:
        match = re.search(r'content="([^"]+)" name="csrf-token"', html)
    if not match:
        match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    return match.group(1) if match else None

def run_e2e_verification():
    print("==================================================")
    print("   IncidentFlow Role-Based E2E Verification       ")
    print("==================================================")
    
    client = app.test_client()
    
    # 1. Unauthenticated root redirect check
    res = client.get("/")
    assert res.status_code == 302, f"Expected redirect to login, got {res.status_code}"
    print("[PASS] 1. Unauthenticated access safely redirects to '/login'")

    # 2. Login as Admin
    login_page = client.get("/login")
    csrf_token = extract_csrf_token(login_page.data.decode())
    res = client.post("/login", data={
        "csrf_token": csrf_token,
        "username": "admin",
        "password": "AdminPassword123!"
    }, follow_redirects=True)
    assert res.status_code == 200, "Admin login failed"
    assert "System Administrator" in res.data.decode()
    print("[PASS] 2. Admin login successful; full operations dashboard displayed")

    # 3. Admin can view all incidents across all agents
    res = client.get("/incidents")
    assert res.status_code == 200
    all_html = res.data.decode()
    assert "INC-0001" in all_html
    assert "INC-0002" in all_html
    assert "INC-0005" in all_html
    print("[PASS] 3. Admin can view all organization incidents")

    # 4. Admin has access to team management and analytics
    res = client.get("/team")
    assert res.status_code == 200
    assert "Engineering Operations Team" in res.data.decode()
    print("[PASS] 4. Admin has full access to Team & Workload directory")

    # Find an incident assigned to Sarah Jenkins (sarah.ops) and one to Alex Rivera (alex.net)
    with app.app_context():
        sarah = User.query.filter_by(username="sarah.ops").first()
        alex = User.query.filter_by(username="alex.net").first()
        sarah_inc = Incident.query.filter_by(assigned_user_id=sarah.id).first()
        alex_inc = Incident.query.filter_by(assigned_user_id=alex.id).first()

    assert sarah_inc is not None and alex_inc is not None, "Seed data missing assigned incidents"

    # 5. Logout Admin and Login as Support Agent (Sarah Jenkins)
    client.get("/logout")
    login_page = client.get("/login")
    csrf_token = extract_csrf_token(login_page.data.decode())
    res = client.post("/login", data={
        "csrf_token": csrf_token,
        "username": "sarah.ops",
        "password": "AgentPass123!"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "Sarah Jenkins" in res.data.decode()
    print("[PASS] 5. Support Agent (Sarah) login successful")

    # 6. Data Isolation: Sarah only sees her own incidents
    res = client.get("/incidents")
    assert res.status_code == 200
    sarah_list = res.data.decode()
    assert sarah_inc.reference_id in sarah_list, f"Sarah's own incident {sarah_inc.reference_id} missing"
    assert alex_inc.reference_id not in sarah_list, f"Data leak! Alex's incident {alex_inc.reference_id} shown to Sarah"
    print(f"[PASS] 6. Data Isolation verified: Sarah sees {sarah_inc.reference_id} but NOT {alex_inc.reference_id}")

    # 7. Agent cannot access Alex's incident via direct URL (returns 403)
    res = client.get(f"/incidents/{alex_inc.id}")
    assert res.status_code == 403, f"Expected 403 for unauthorized access, got {res.status_code}"
    print(f"[PASS] 7. Unauthorized URL access blocked: Sarah cannot view Alex's incident #{alex_inc.id} (HTTP 403)")

    # 8. Agent cannot access Alex's incident via API (returns 403)
    res = client.get(f"/api/incidents/{alex_inc.id}")
    assert res.status_code == 403, f"Expected 403 API response, got {res.status_code}"
    print(f"[PASS] 8. Unauthorized API access blocked: Sarah cannot fetch Alex's incident #{alex_inc.id} (HTTP 403)")

    # 9. Agent cannot edit incidents (Edit option removed, route blocked)
    res = client.get(f"/incidents/{sarah_inc.id}/edit", follow_redirects=True)
    assert "Access denied" in res.data.decode()
    print("[PASS] 9. Edit incident route strictly blocked for Support Agents (HTTP 403/Redirect)")

    # 10. Agent cannot create incidents
    res = client.get("/incidents/create", follow_redirects=True)
    assert "Access denied" in res.data.decode()
    res = client.post("/api/incidents", json={"title": "Unauthorized"})
    assert res.status_code == 403
    print("[PASS] 10. Incident creation strictly blocked for Support Agents (Web & API 403)")

    # 11. Agent cannot delete incidents
    inc_page = client.get(f"/incidents/{sarah_inc.id}")
    csrf_token = extract_csrf_token(inc_page.data.decode())
    res = client.post(f"/incidents/{sarah_inc.id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True)
    assert "Access denied" in res.data.decode()
    res = client.delete(f"/api/incidents/{sarah_inc.id}")
    assert res.status_code == 403
    print("[PASS] 11. Incident deletion strictly blocked for Support Agents (Web & API 403)")

    # 12. Agent cannot access Team Management
    res = client.get("/team", follow_redirects=True)
    assert "Access denied" in res.data.decode()
    print("[PASS] 12. Team Management strictly blocked for Support Agents (HTTP 403/Redirect)")

    # 13. Agent CAN update status of their assigned incident
    inc_page = client.get(f"/incidents/{sarah_inc.id}")
    csrf_token = extract_csrf_token(inc_page.data.decode())
    res = client.post(f"/incidents/{sarah_inc.id}/status", data={
        "csrf_token": csrf_token,
        "status": "In Progress",
        "comment": "Sarah active investigation update"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "Status updated" in res.data.decode()
    print(f"[PASS] 13. Support Agent successfully updated status on assigned incident {sarah_inc.reference_id}")

    # 14. Agent analytics shows only personal metrics
    res = client.get("/analytics")
    assert res.status_code == 200
    analytics_html = res.data.decode()
    assert "Sarah Jenkins" in analytics_html
    assert "Alex Rivera" not in analytics_html
    print("[PASS] 14. Support Agent analytics isolated: Sarah sees her metrics, Alex is hidden")

    print("==================================================")
    print("   ALL 14 ROLE-BASED VERIFICATION CHECKS PASSED!  ")
    print("==================================================")

if __name__ == "__main__":
    run_e2e_verification()
