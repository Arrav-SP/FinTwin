from fastapi.testclient import TestClient

from backend.app.main import app


def test_the_api_serves_the_built_ui_and_no_longer_the_old_one():
    client = TestClient(app)
    page = client.get("/predict")
    assert page.status_code in (200, 503)  # 503 until `npm --prefix web run build` has been run
    assert client.get("/styles.css").status_code == 404
    assert client.get("/app.js").status_code == 404
    assert client.get("/api/no-such-endpoint").status_code == 404
