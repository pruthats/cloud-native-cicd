import json
import os
import urllib.error
import urllib.request

from flask import Flask, jsonify, request

app = Flask(__name__)

COURSE_SERVICE_URL = os.getenv("COURSE_SERVICE_URL", "http://course:5001")

REGISTRATIONS = []

def fetch_course(course_id):
    url = f"{COURSE_SERVICE_URL}/courses/{course_id}"
    with urllib.request.urlopen(url, timeout=2) as response:
        payload = json.loads(response.read().decode())
        return payload["course"]


@app.get("/health")
def health():
    return jsonify(status="ok", service="registration")


@app.get("/courses")
def list_courses():
    try:
        with urllib.request.urlopen(f"{COURSE_SERVICE_URL}/courses", timeout=2) as response:
            return jsonify(json.loads(response.read().decode()))
    except (urllib.error.URLError, TimeoutError) as error:
        return jsonify(error="Course service is unavailable", detail=str(error)), 503


@app.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    user = body.get("user")
    course_id = body.get("course_id")

    if not user or not course_id:
        return jsonify(error="'user' and 'course_id' are required"), 400

    try:
        course = fetch_course(course_id)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return jsonify(error="Course not found", course_id=course_id), 404
        return jsonify(error="Course service error", detail=str(error)), 502
    except (urllib.error.URLError, TimeoutError) as error:
        return jsonify(error="Course service is unavailable", detail=str(error)), 503

    enrollment = {"user": user, "course": course}
    REGISTRATIONS.append(enrollment)
    return jsonify(message="Registration successful", enrollment=enrollment), 201


@app.get("/registrations")
def list_registrations():
    return jsonify(registrations=REGISTRATIONS, count=len(REGISTRATIONS))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
