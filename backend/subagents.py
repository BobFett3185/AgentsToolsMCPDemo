import os
from typing import Any, Callable

from dotenv import load_dotenv

from backend.data_tools import (
    ELIGIBILITY_TOOL_SCHEMAS,
    REVIEWS_TOOL_SCHEMAS,
    call_eligibility_tool,
    call_reviews_tool,
)


load_dotenv() # needed when this file reads GEMINI_MODEL from .env

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
MAX_TOOL_ROUNDS = 5


ELIGIBILITY_AGENT_INSTRUCTION = """
You are the eligibility sub-agent for a UTD course planning demo.
Your job is to answer questions about course details, sections, prerequisites,
and whether a student appears eligible based on completed courses.

Use GetStudentHistory for student records, GetCourseCatalog for broad schedule
planning, and GetCourseInfo for details about specific courses.
For schedule requests, recommend only courses that appear in GetCourseCatalog.
Do not invent course codes. If the user does not say how many courses they want,
recommend 4 courses.
Return a short, factual answer that the orchestrator agent can use.
"""

REVIEWS_AGENT_INSTRUCTION = """
You are the reviews sub-agent for a UTD course planning demo.
Your job is to answer questions about professor review trends.

Use GetRMPScore to get mock review data. Pass a professor name when asking about
one professor. Pass a course code when comparing professors for that course.
Return a short, factual answer that the orchestrator agent can use.
"""


# These functions run our two sub-agents. Each sub-agent has its own tools.
def run_subagent(
    agent_name: str,
    instruction: str,
    prompt: str,
    tool_schemas: list[dict[str, Any]],
    tool_handler: Callable[[str, dict[str, Any]], dict[str, Any]],
    trace: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run a small Gemini agent that can call its own tools."""
    add_trace(trace, agent_name, "start", {"prompt": prompt})

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        add_trace(trace, agent_name, "error", {"message": "Missing dependencies"})
        return {
            "status": "error",
            "answer": "Install dependencies with `pip install -r requirements.txt`.",
            "used_tools": [],
        }

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    config = types.GenerateContentConfig(
        system_instruction=instruction,
        tools=[types.Tool(function_declarations=tool_schemas)],
    )
    used_tools: list[str] = []
    add_trace(trace, agent_name, "model_selected", {"model": MODEL_NAME})

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            add_trace(trace, agent_name, "llm_request", {"model": MODEL_NAME})
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=config,
            )
        except Exception as error:
            add_trace(trace, agent_name, "llm_error", {"error": str(error)})
            return {
                "status": "error",
                "answer": f"Sub-agent Gemini API error: {error}",
                "used_tools": used_tools,
            }

        function_calls = getattr(response, "function_calls", None) or []
        if not function_calls:
            add_trace(trace, agent_name, "final_answer", {"used_tools": used_tools})
            return {
                "status": "success",
                "answer": response_text(response),
                "used_tools": used_tools,
                "model": MODEL_NAME,
            }

        contents.append(response.candidates[0].content)
        tool_results = []
        add_trace(
            trace,
            agent_name,
            "tool_calls_requested",
            {"tools": [call.name for call in function_calls]},
        )

        for call in function_calls:
            args = dict(call.args or {})
            add_trace(
                trace,
                agent_name,
                "tool_call_started",
                {"tool": call.name, "args": args},
            )
            tool_result = tool_handler(call.name, args)
            used_tools.append(call.name)
            add_trace(
                trace,
                agent_name,
                "tool_call_finished",
                {"tool": call.name, "status": tool_result.get("status")},
            )
            tool_results.append(
                types.Part.from_function_response(name=call.name, response=tool_result)
            )

        contents.append(types.Content(role="tool", parts=tool_results))

    add_trace(trace, agent_name, "max_tool_rounds_reached", {"used_tools": used_tools})
    return {
        "status": "error",
        "answer": "Sub-agent kept asking for tools and did not produce a final answer.",
        "used_tools": used_tools,
    }


def run_eligibility_agent(
    question: str,
    student_id: str,
    trace: list[dict[str, Any]],
) -> dict[str, Any]:
    """Sub-agent for student history, course info, and prerequisite checks."""
    prompt = (
        f"Student ID: {student_id}\n"
        f"Question from orchestrator: {question}\n\n"
        "Use GetStudentHistory, GetCourseCatalog, and GetCourseInfo when helpful."
    )
    return run_subagent(
        "eligibility_agent",
        ELIGIBILITY_AGENT_INSTRUCTION,
        prompt,
        ELIGIBILITY_TOOL_SCHEMAS,
        call_eligibility_tool,
        trace,
    )


def run_reviews_agent(question: str, trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Sub-agent for professor review lookups."""
    prompt = (
        f"Question from orchestrator: {question}\n\n"
        "Use GetRMPScore when professor review data would help. "
        "If comparing sections for a course, pass the course code."
    )
    return run_subagent(
        "reviews_agent",
        REVIEWS_AGENT_INSTRUCTION,
        prompt,
        REVIEWS_TOOL_SCHEMAS,
        call_reviews_tool,
        trace,
    )


def response_text(response: Any) -> str:
    """Read only text parts, avoiding SDK warnings about function-call parts."""
    try:
        parts = response.candidates[0].content.parts
    except (AttributeError, IndexError):
        return "Gemini did not return a readable response."

    text_parts = [part.text for part in parts if getattr(part, "text", None)]
    if not text_parts:
        return "Gemini did not return a text response."

    return "\n".join(text_parts)


def add_trace(
    trace: list[dict[str, Any]],
    agent: str,
    event: str,
    details: dict[str, Any] | None = None,
) -> None:
    trace.append(
        {
            "step": len(trace) + 1,
            "agent": agent,
            "event": event,
            "details": details or {},
        }
    )
