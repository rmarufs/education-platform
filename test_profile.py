import sys
import logging
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStudent

client = TestClient(app)
db = SessionLocal()

# Find a student who is in an organization
org_student = db.query(OrganizationStudent).first()
if not org_student:
    print("No org student found")
    sys.exit(0)

student = db.query(User).filter(User.id == org_student.student_id).first()
current_org = db.query(Organization).filter(Organization.id == org_student.organization_id).first()

# Find another organization
other_org = db.query(Organization).filter(Organization.id != current_org.id).first()

if not other_org:
    print("No other org found")
    sys.exit(0)

print(f"Student: {student.email}, Current Org: {current_org.name}, Other Org: {other_org.name}")

# Simulate login
response = client.post("/auth/login", data={"username": student.email, "password": "password123"})
if response.status_code != 200:
    print("Login failed, trying another way...")

# Just mock the session
with client.session_transaction() as sess:
    sess["user_id"] = student.id

response = client.get(f"/organization/{other_org.id}")
print("Status Code:", response.status_code)
content = response.text

if "currentStudentOrgName = null" in content:
    print("ERROR: currentStudentOrgName is null!")
elif "currentStudentOrgName =" in content:
    import re
    match = re.search(r'const currentStudentOrgName = (.*?);', content)
    if match:
        print("currentStudentOrgName IS SET TO:", match.group(1))
else:
    print("currentStudentOrgName not found in HTML!")

