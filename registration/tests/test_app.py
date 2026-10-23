import io
import json
import urllib.error

import pytest

import app as registration


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_json(payload):
    return FakeResponse(json.dumps(payload).encode())


@pytest.fixture()
def client():
    registration.app.config["TESTING"] = True
    registration.REGISTRATIONS.clear()
    return registration.app.test_client()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "service": "registration"}


def test_register_requires_fields(client):
    res = client.post("/register", json={"user": "alice"})
    assert res.status_code == 400


def test_register_success(client, monkeypatch):
    course = {"id": "CS01", "title": "Cloud Native Applications", "seats": 30}
    monkeypatch.setattr(
        registration.urllib.request, "urlopen",
        lambda *a, **k: fake_json({"course": course}),
    )
    res = client.post("/register", json={"user": "alice", "course_id": "CS01"})
    assert res.status_code == 201
    assert res.get_json()["enrollment"] == {"user": "alice", "course": course}

    listing = client.get("/registrations").get_json()
    assert listing["count"] == 1


def test_register_unknown_course(client, monkeypatch):
    def raise_404(*a, **k):
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)

    monkeypatch.setattr(registration.urllib.request, "urlopen", raise_404)
    res = client.post("/register", json={"user": "alice", "course_id": "XX"})
    assert res.status_code == 404


def test_register_course_service_down(client, monkeypatch):
    def raise_down(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(registration.urllib.request, "urlopen", raise_down)
    res = client.post("/register", json={"user": "alice", "course_id": "CS01"})
    assert res.status_code == 503


def test_list_courses_proxies_course_service(client, monkeypatch):
    payload = {"courses": [{"id": "CS01"}]}
    monkeypatch.setattr(
        registration.urllib.request, "urlopen", lambda *a, **k: fake_json(payload)
    )
    res = client.get("/courses")
    assert res.status_code == 200
    assert res.get_json() == payload
