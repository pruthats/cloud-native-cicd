import os

from flask import Flask, jsonify

app = Flask(__name__)

COURSES = {
    "CS01": {"id": "CS01", "title": "Cloud Native Applications", "seats": 30},
    "CS02": {"id": "CS02", "title": "Microservice Architecture", "seats": 25},
    "CS03": {"id": "CS03", "title": "MLOps", "seats": 20},
}


@app.get("/health")
def health():
    return jsonify(status="ok", service="course")


@app.get("/courses")
def list_courses():
    return jsonify(courses=list(COURSES.values()))


@app.get("/courses/<course_id>")
def get_course(course_id):
    course = COURSES.get(course_id.upper())
    if course is None:
        return jsonify(error="Course not found", course_id=course_id), 404
    return jsonify(course=course)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")))
