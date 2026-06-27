import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"


# These are the functions that implement our tools.
# In a real app these could call databases or MCP servers instead.
# They grab mock data from JSON and return it in a tool-friendly shape.

def get_course_info(courseCode: str) -> dict[str, Any]:
    """Return course metadata and all sections for a courseCode like CS 3345."""
    courses = load_json("courses.json")
    course_code = courseCode.strip().upper()
    course = courses.get(course_code)

    if course is None:
        return {"status": "not_found", "courseCode": course_code}

    return {"status": "success", "courseCode": course_code, **course}


def get_student_history(studentID: str) -> dict[str, Any]:
    """Return a student's year and completed courses."""
    students = load_json("students.json")
    student = students.get(studentID)

    if student is None:
        return {"status": "not_found", "studentID": studentID}

    return {"status": "success", "studentID": studentID, **student}


def get_rmp_score(professor: str) -> dict[str, Any]:
    """Return mock professor review data for a professor or course code."""
    reviews = load_json("rmp_reviews.json")
    lookup = professor.strip()
    lookup_key = lookup.lower()
    professor_reviews = reviews.get(lookup_key)

    if professor_reviews is not None:
        return {
            "status": "success",
            "professor": lookup,
            "courses": professor_reviews,
        }

    course_code = lookup.upper()
    course_reviews = {}
    for professor_name, professor_courses in reviews.items():
        if course_code in professor_courses:
            course_reviews[professor_name] = professor_courses[course_code]

    if course_reviews:
        return {
            "status": "success",
            "courseCode": course_code,
            "professors": course_reviews,
        }

    return {
        "status": "not_found",
        "lookup": lookup,
        "hint": "Use a professor name like Grace Hopper or a course code like CS 3345.",
    }


def get_course_catalog() -> dict[str, Any]:
    """Return the mock course catalog with course codes, titles, and prerequisites."""
    courses = load_json("courses.json")
    catalog = []

    for course_code, course in courses.items():
        catalog.append(
            {
                "courseCode": course_code,
                "title": course["title"],
                "prerequisites": course.get("prerequisites", []),
                "professors": [
                    section["professor"] for section in course.get("sections", [])
                ],
            }
        )

    return {"status": "success", "courses": catalog}


# These handlers are what the sub-agent loops call after Gemini asks for a tool.
def call_eligibility_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "GetStudentHistory":
        return get_student_history(args["studentID"])
    if name == "GetCourseCatalog":
        return get_course_catalog()
    if name == "GetCourseInfo":
        return get_course_info(args["courseCode"])

    return {"status": "error", "message": f"Unknown eligibility tool: {name}"}


def call_reviews_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "GetRMPScore":
        return get_rmp_score(args["professor"])

    return {"status": "error", "message": f"Unknown reviews tool: {name}"}


def load_json(file_name: str) -> dict[str, Any]:
    with (DATA_DIR / file_name).open(encoding="utf-8") as file:
        return json.load(file)


# Tool schemas in the format Gemini can understand.
ELIGIBILITY_TOOL_SCHEMAS = [
    {
        "name": "GetCourseCatalog",
        "description": "Get the available mock course catalog for schedule planning.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "GetCourseInfo",
        "description": "Get metadata for a UTD course across all sections.",
        "parameters": {
            "type": "object",
            "properties": {
                "courseCode": {
                    "type": "string",
                    "description": "Course number like CS 3345.",
                }
            },
            "required": ["courseCode"],
        },
    },
    {
        "name": "GetStudentHistory",
        "description": "Get a student's year and completed courses.",
        "parameters": {
            "type": "object",
            "properties": {
                "studentID": {
                    "type": "string",
                    "description": "Student id like demo-student.",
                }
            },
            "required": ["studentID"],
        },
    },
]


REVIEWS_TOOL_SCHEMAS = [
    {
        "name": "GetRMPScore",
        "description": (
            "Get mock Rate My Professors review data by professor name or course code. "
            "For comparing professors for a course, pass the course code."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "professor": {
                    "type": "string",
                    "description": "Professor name like Grace Hopper or course code like CS 3345.",
                },
            },
            "required": ["professor"],
        },
    },
]
