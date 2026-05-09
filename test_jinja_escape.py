from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from fastapi import FastAPI
from starlette.requests import Request

app = FastAPI()
templates = Jinja2Templates(directory="templates")

class MockOrg:
    def __init__(self, name):
        self.name = name

@app.get("/")
def test_route(request: Request):
    return templates.TemplateResponse(
        "organization/public_profile.html",
        {
            "request": request,
            "user": type('User', (), {'is_student': True})(),
            "org": type('Org', (), {'id': 1, 'name': 'Test', 'status': 'approved'})(),
            "org_teachers": [],
            "courses": [],
            "avg_rating": 5.0,
            "user_application": None,
            "user_in_any_org": False,
            "user_student_membership": None,
            "current_student_org": MockOrg("Test Org")
        }
    )

client = TestClient(app)
try:
    response = client.get("/")
    content = response.text
    import re
    match = re.search(r'const currentStudentOrgName = (.*?);', content)
    if match:
        print("MATCH:", match.group(1))
except Exception as e:
    print("ERROR:", e)

