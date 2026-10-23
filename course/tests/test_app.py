import pytest

from app import app


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "service": "course"}


def test_list_courses(client):
    res = client.get("/courses")
    assert res.status_code == 200
    courses = res.get_json()["courses"]
    assert {c["id"] for c in courses} == {"CS01", "CS02", "CS03"}


def test_get_course_is_case_insensitive(client):
    res = client.get("/courses/cs01")
    assert res.status_code == 200
    assert res.get_json()["course"]["title"] == "Cloud Native Applications"


def test_get_unknown_course_returns_404(client):
    res = client.get("/courses/NOPE")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Course not found"
