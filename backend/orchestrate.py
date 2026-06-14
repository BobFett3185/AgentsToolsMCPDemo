import os
import re
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


MODEL_NAME = "gemini-1.5-flash"
DATA_DIR = Path(__file__).resolve().parent / "data"

load_dotenv()


SYSTEM_INSTRUCTION = """
You are a UTD course planner assistant for hackathon workshop demos.
Help students reason about courses, prerequisites, sections, professors,
and schedule tradeoffs. Use tools when course data, professor reviews, or
student history would help answer the question.

Be concise and practical. If prerequisite data is available, compare it with
the student's completed courses. If professor review data is available,
summarize the trend instead of dumping every review.
"""

# Tiny simulated memory. A database can replace this later.
memory: list[dict[str, str]] = []


def chat(message: str, student_id: str = "demo-student") -> dict[str, Any]:
    """Called by FastAPI when the user sends a chat message."""
    memory.append({"role": "user", "content": message})

    if os.getenv("GOOGLE_API_KEY"):
        reply, used_tools = run_gemini_agent(message, student_id)
    else:
        reply, used_tools = run_without_llm(message, student_id)

    memory.append({"role": "assistant", "content": reply})

    return {"reply": reply, "model": MODEL_NAME, "used_tools": used_tools}


def get_tool_schemas() -> list[dict[str, Any]]:
    return TOOL_SCHEMAS


def run_gemini_agent(message: str, student_id: str) -> tuple[str, list[str]]:
    """Send the user message to Gemini and let it call our tools."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        reply, used_tools = run_without_llm(message, student_id)
        return (
            f"{reply}\n\nInstall dependencies with `pip install -r requirements.txt` to enable Gemini calls.",
            used_tools,
        )

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    used_tools: list[str] = []

    prompt = (
        f"Student ID: {student_id}\n"
        f"User question: {message}\n\n"
        "Use the tools when they help. For prerequisite questions, call "
        "GetPrevClasses and GetCourseInfo."
    )

    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[types.Tool(function_declarations=TOOL_SCHEMAS)],
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=config,
    )

    function_calls = getattr(response, "function_calls", None) or []
    if not function_calls:
        return response.text or "Gemini did not return a text response.", used_tools

    contents.append(response.candidates[0].content)
    tool_results = []

    for call in function_calls:
        tool_result = call_tool(call.name, dict(call.args or {}))
        used_tools.append(call.name)
        tool_results.append(
            types.Part.from_function_response(name=call.name, response=tool_result)
        )

    contents.append(types.Content(role="tool", parts=tool_results))

    final_response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=config,
    )
    return final_response.text or "Gemini did not return a final text response.", used_tools


def run_without_llm(message: str, student_id: str) -> tuple[str, list[str]]:
    """Simple mode for teaching before API keys are added."""
    course_number = extract_course_number(message) or "CS 3345"
    course_info = get_course_info(course_number)
    student_info = get_prev_classes(student_id)

    if course_info["status"] != "success":
        return f"I do not have mock data for {course_number}.", ["GetCourseInfo"]

    completed = set(student_info.get("completedCourses", []))
    missing = [
        course
        for course in course_info.get("prerequisites", [])
        if course not in completed
    ]

    if missing:
        prereq_sentence = f"You are missing {', '.join(missing)}."
    else:
        prereq_sentence = "You meet the listed prerequisites."

    sections = []
    for section in course_info["sections"]:
        sections.append(
            f"{section['section']} with {section['professor']} on "
            f"{', '.join(section['days'])} from {section['time']}"
        )

    reply = (
        f"{course_info['courseNumber']} is {course_info['title']}. "
        f"{prereq_sentence}\n\nSections:\n- " + "\n- ".join(sections)
    )
    return reply, ["GetCourseInfo", "GetPrevClasses"]


def get_course_info(courseNumber: str) -> dict[str, Any]:
    """Return course metadata and all sections for a course like CS 3345."""
    courses = load_json("courses.json")
    course_number = courseNumber.strip().upper()
    course = courses.get(course_number)

    if course is None:
        return {"status": "not_found", "courseNumber": course_number}

    return {"status": "success", "courseNumber": course_number, **course}


def get_prev_classes(studentID: str) -> dict[str, Any]:
    """Return a student's completed courses."""
    students = load_json("students.json")
    student = students.get(studentID)

    if student is None:
        return {"status": "not_found", "studentID": studentID}

    return {"status": "success", "studentID": studentID, **student}


def get_rmp(professor: str, course: str) -> dict[str, Any]:
    """Return mock professor review data."""
    reviews = load_json("rmp_reviews.json")
    professor_reviews = reviews.get(professor.strip().lower())

    if professor_reviews is None:
        return {"status": "not_found", "professor": professor, "course": course}

    course_reviews = professor_reviews.get(course.strip().upper())
    if course_reviews is None:
        return {"status": "not_found", "professor": professor, "course": course}

    return {
        "status": "success",
        "professor": professor,
        "course": course.strip().upper(),
        **course_reviews,
    }


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "GetCourseInfo":
        return get_course_info(args["courseNumber"])
    if name == "GetPrevClasses":
        return get_prev_classes(args["studentID"])
    if name == "GetRMP":
        return get_rmp(args["professor"], args["course"])

    return {"status": "error", "message": f"Unknown tool: {name}"}


def load_json(file_name: str) -> dict[str, Any]:
    with (DATA_DIR / file_name).open(encoding="utf-8") as file:
        return json.load(file)


def extract_course_number(message: str) -> str | None:
    match = re.search(r"\b([A-Za-z]{2,4})\s*-?\s*(\d{4})\b", message)
    if match is None:
        return None

    return f"{match.group(1).upper()} {match.group(2)}"


TOOL_SCHEMAS = [
    {
        "name": "GetCourseInfo",
        "description": "Get metadata for a UTD course across all sections.",
        "parameters": {
            "type": "object",
            "properties": {
                "courseNumber": {
                    "type": "string",
                    "description": "Course number like CS 3345.",
                }
            },
            "required": ["courseNumber"],
        },
    },
    {
        "name": "GetPrevClasses",
        "description": "Get the courses a student has already completed.",
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
    {
        "name": "GetRMP",
        "description": "Get mock Rate My Professors review data.",
        "parameters": {
            "type": "object",
            "properties": {
                "professor": {"type": "string"},
                "course": {"type": "string"},
            },
            "required": ["professor", "course"],
        },
    },
]


try:
    from google.adk.agents.llm_agent import Agent

    root_agent = Agent(
        model=MODEL_NAME,
        name="utd_course_planner_agent",
        instruction=SYSTEM_INSTRUCTION,
        tools=[get_course_info, get_prev_classes, get_rmp],
    )
except ImportError:
    root_agent = None
