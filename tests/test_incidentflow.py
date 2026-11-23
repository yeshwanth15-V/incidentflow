import unittest
import os
import json
from datetime import datetime, timezone, timedelta

# Set testing configuration environment
os.environ["SECRET_KEY"] = "test-secret-key-for-automated-verification"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "false"
os.environ["SMTP_ENABLED"] = "false"

from app import create_app
from database import db
from models.user import User
from models.incident import Incident
from models.activity import IncidentActivity
from services.sla_service import calculate_due_date, get_sla_metrics

class IncidentFlowRoleWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # 1. Admin
        self.admin = User(
            username="admin_user",
            email="admin@incidentflow.com",
            full_name="Lead Administrator",
            role="Admin",
            is_active_account=True
        )
        self.admin.set_password("AdminSecurePassword123!")
        db.session.add(self.admin)

        # 2. Support Agent A
        self.agent_a = User(
            username="agent_a",
            email="agent_a@incidentflow.com",
            full_name="Agent Alpha",
            role="Support Agent",
            is_active_account=True
        )
        self.agent_a.set_password("AgentPass123!")
        db.session.add(self.agent_a)

        # 3. Support Agent B
        self.agent_b = User(
            username="agent_b",
            email="agent_b@incidentflow.com",
            full_name="Agent Beta",
            role="Support Agent",
            is_active_account=True
        )
        self.agent_b.set_password("AgentPass123!")
        db.session.add(self.agent_b)

        db.session.commit()

        # Seed incidents for Agent A and Agent B
        now = datetime.now(timezone.utc)
        self.inc_a = Incident(
            title="Database Latency Spike Alpha",
            description="Agent A's assigned task",
            priority="Critical",
            status="Open",
            category="Database",
            assigned_user_id=self.agent_a.id,
            assigned_to=self.agent_a.full_name,
            created_at=now,
            due_date=calculate_due_date("Critical", now)
        )
        self.inc_b = Incident(
            title="VPN Connection Dropping Beta",
            description="Agent B's assigned task",
            priority="High",
            status="In Progress",
            category="Network",
            assigned_user_id=self.agent_b.id,
            assigned_to=self.agent_b.full_name,
            created_at=now,
            due_date=calculate_due_date("High", now)
        )
        self.inc_unassigned = Incident(
            title="Firewall Audit Unassigned",
            description="Triage queue item",
            priority="Low",
            status="Open",
            category="Security",
            assigned_user_id=None,
            assigned_to=None,
            created_at=now,
            due_date=calculate_due_date("Low", now)
        )
        db.session.add_all([self.inc_a, self.inc_b, self.inc_unassigned])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, username, password):
        return self.client.post("/login", data={
            "username": username,
            "password": password
        }, follow_redirects=True)

    def logout(self):
        return self.client.get("/logout", follow_redirects=True)

    # 1. Admin Workflow: Admin has complete control
    def test_admin_sees_all_incidents_and_can_assign(self):
        self.login("admin_user", "AdminSecurePassword123!")

        res = self.client.get("/incidents")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Database Latency Spike Alpha", res.data)
        self.assertIn(b"VPN Connection Dropping Beta", res.data)
        self.assertIn(b"Firewall Audit Unassigned", res.data)

        # Admin assigns incident to Agent A
        res = self.client.post(f"/incidents/{self.inc_unassigned.id}/assign", data={
            "assigned_user_id": self.agent_a.id
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(self.inc_unassigned)
        self.assertEqual(self.inc_unassigned.assigned_user_id, self.agent_a.id)

    def test_admin_can_create_edit_delete(self):
        self.login("admin_user", "AdminSecurePassword123!")

        # Create
        res = self.client.post("/incidents/create", data={
            "title": "Admin Created Incident",
            "description": "Full admin test",
            "priority": "High",
            "category": "Software",
            "assigned_user_id": self.agent_a.id
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        created = Incident.query.filter_by(title="Admin Created Incident").first()
        self.assertIsNotNone(created)

        # Edit
        res = self.client.post(f"/incidents/{created.id}/edit", data={
            "title": "Admin Created Incident - Edited",
            "description": "Updated description",
            "priority": "Medium",
            "category": "Software",
            "status": "In Progress",
            "assigned_user_id": self.agent_b.id
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(created)
        self.assertEqual(created.title, "Admin Created Incident - Edited")
        self.assertEqual(created.assigned_user_id, self.agent_b.id)

        # Delete
        res = self.client.post(f"/incidents/{created.id}/delete", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(db.session.get(Incident, created.id))

    # 2. Support Agent Data Isolation: Agent A vs Agent B
    def test_agent_a_sees_only_assigned_incidents(self):
        self.login("agent_a", "AgentPass123!")

        res = self.client.get("/incidents")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Database Latency Spike Alpha", res.data)
        # MUST NEVER see Agent B's or unassigned incidents
        self.assertNotIn(b"VPN Connection Dropping Beta", res.data)
        self.assertNotIn(b"Firewall Audit Unassigned", res.data)

        # Via JSON list
        res = self.client.get("/incidents", headers={"Accept": "application/json"})
        self.assertEqual(res.status_code, 200)
        items = json.loads(res.data)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], self.inc_a.id)

    def test_agent_b_sees_only_assigned_incidents(self):
        self.login("agent_b", "AgentPass123!")

        res = self.client.get("/incidents")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"VPN Connection Dropping Beta", res.data)
        self.assertNotIn(b"Database Latency Spike Alpha", res.data)
        self.assertNotIn(b"Firewall Audit Unassigned", res.data)

    def test_agent_a_cannot_access_agent_b_incident_via_url_or_api(self):
        self.login("agent_a", "AgentPass123!")

        # Direct Web URL to Agent B's incident
        res = self.client.get(f"/incidents/{self.inc_b.id}")
        self.assertEqual(res.status_code, 403)

        # Direct API GET to Agent B's incident
        res = self.client.get(f"/api/incidents/{self.inc_b.id}")
        self.assertEqual(res.status_code, 403)
        self.assertIn("Access denied", res.get_json().get("error", ""))

        # Direct Web URL to their own incident must succeed
        res = self.client.get(f"/incidents/{self.inc_a.id}")
        self.assertEqual(res.status_code, 200)

    # 3. Agents Cannot Create or Delete Incidents
    def test_agents_cannot_create_incidents(self):
        self.login("agent_a", "AgentPass123!")

        # GET /incidents/create
        res = self.client.get("/incidents/create", follow_redirects=True)
        self.assertIn(b"Access denied", res.data)

        # POST /incidents/create
        res = self.client.post("/incidents/create", data={
            "title": "Agent Attempted Incident",
            "description": "Should fail",
            "priority": "Low",
            "category": "General"
        }, follow_redirects=True)
        self.assertIn(b"Access denied", res.data)

        # POST /incidents (Legacy / Web route)
        res = self.client.post("/incidents", data={
            "title": "Agent Attempted Incident 2",
            "description": "Should fail",
            "priority": "Low",
            "category": "General"
        })
        self.assertEqual(res.status_code, 403)

        # POST /api/incidents
        res = self.client.post("/api/incidents", json={
            "title": "Agent Attempted Incident 3",
            "description": "Should fail"
        })
        self.assertEqual(res.status_code, 403)

    def test_agents_cannot_delete_incidents(self):
        self.login("agent_a", "AgentPass123!")

        # Web delete
        res = self.client.post(f"/incidents/{self.inc_a.id}/delete", follow_redirects=True)
        self.assertIn(b"Access denied", res.data)
        self.assertIsNotNone(db.session.get(Incident, self.inc_a.id))

        # API delete
        res = self.client.delete(f"/api/incidents/{self.inc_a.id}")
        self.assertEqual(res.status_code, 403)
        self.assertIsNotNone(db.session.get(Incident, self.inc_a.id))

    # 4. Agents Cannot Edit Incident Fields Other Than Status
    def test_agents_cannot_access_edit_form(self):
        self.login("agent_a", "AgentPass123!")

        res = self.client.get(f"/incidents/{self.inc_a.id}/edit", follow_redirects=True)
        self.assertIn(b"Access denied", res.data)

        res = self.client.post(f"/incidents/{self.inc_a.id}/edit", data={
            "title": "Hacked Title",
            "description": "Hacked",
            "priority": "Low",
            "status": "Closed",
            "category": "General"
        }, follow_redirects=True)
        self.assertIn(b"Access denied", res.data)
        db.session.refresh(self.inc_a)
        self.assertNotEqual(self.inc_a.title, "Hacked Title")

    def test_agents_cannot_modify_fields_via_api(self):
        self.login("agent_a", "AgentPass123!")

        # Attempt to modify title & priority
        res = self.client.put(f"/api/incidents/{self.inc_a.id}", json={
            "title": "Hacked via API",
            "priority": "Low"
        })
        self.assertEqual(res.status_code, 403)
        db.session.refresh(self.inc_a)
        self.assertNotEqual(self.inc_a.title, "Hacked via API")

    def test_agents_can_update_status_of_assigned_incident(self):
        self.login("agent_a", "AgentPass123!")

        # Update status via Web form
        res = self.client.post(f"/incidents/{self.inc_a.id}/status", data={
            "status": "In Progress",
            "comment": "Investigating replica latency"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(self.inc_a)
        self.assertEqual(self.inc_a.status, "In Progress")

        # Update status via API
        res = self.client.put(f"/api/incidents/{self.inc_a.id}", json={
            "status": "Resolved"
        })
        self.assertEqual(res.status_code, 200)
        db.session.refresh(self.inc_a)
        self.assertEqual(self.inc_a.status, "Resolved")
        self.assertIsNotNone(self.inc_a.resolved_at)

    def test_agents_cannot_update_status_of_others_incidents(self):
        self.login("agent_a", "AgentPass123!")

        res = self.client.post(f"/incidents/{self.inc_b.id}/status", data={
            "status": "Resolved"
        })
        self.assertEqual(res.status_code, 403)
        db.session.refresh(self.inc_b)
        self.assertNotEqual(self.inc_b.status, "Resolved")

    # 5. Agents Cannot Access Team Management
    def test_agents_cannot_access_team(self):
        self.login("agent_a", "AgentPass123!")

        res = self.client.get("/team", follow_redirects=True)
        self.assertIn(b"Access denied", res.data)

        res = self.client.get("/team/create", follow_redirects=True)
        self.assertIn(b"Access denied", res.data)

    # 6. Role-Specific Analytics & SLA
    def test_role_specific_dashboard(self):
        # Admin dashboard shows total=3
        self.login("admin_user", "AdminSecurePassword123!")
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Operations Dashboard", res.data)
        self.assertIn(b"3", res.data)  # Total 3

        # Agent A dashboard shows ONLY Agent A's incidents (total=1)
        self.logout()
        self.login("agent_a", "AgentPass123!")
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Database Latency Spike Alpha", res.data)
        self.assertNotIn(b"VPN Connection Dropping Beta", res.data)
        self.assertNotIn(b"Firewall Audit Unassigned", res.data)

    def test_role_specific_analytics_page(self):
        # Admin analytics shows all incidents and all team members
        self.login("admin_user", "AdminSecurePassword123!")
        res = self.client.get("/analytics")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Agent Alpha", res.data)
        self.assertIn(b"Agent Beta", res.data)

        # Agent A analytics shows ONLY Agent A and hides Agent B
        self.logout()
        self.login("agent_a", "AgentPass123!")
        res = self.client.get("/analytics")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Agent Alpha", res.data)
        self.assertNotIn(b"Agent Beta", res.data)

if __name__ == "__main__":
    unittest.main()
