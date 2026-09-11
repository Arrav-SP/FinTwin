from fastapi.testclient import TestClient

from backend.app.main import app


def test_frontend_shell_and_assets_are_served():
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    assert "FinTwin" in page.text
    assert client.get("/assets/styles.css").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
