import os
from typing import Any

from dotenv import load_dotenv

from backend.subagents import run_eligibility_agent, run_reviews_agent


load_dotenv() # needed to get API keys from the .env file

# Grab our model from .env.
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
MAX_TOOL_ROUNDS = 5

# Instructions for the top-level orchestrator agent.
ORCHESTRATOR_INSTRUCTION = """
You are a UTD course planner assistant for hackathon workshop demos.
Help students reason about courses, prerequisites, sections, professors,
and schedule tradeoffs.

You have two sub-agents exposed as tools:
- EligibilityAgent checks course info, prerequisites, and student history.
- ReviewsAgent checks mock professor review data.

Use the sub-agents when their information would help answer the question.
Be concise and practical. If prerequisite data is available, compare it with
the student's completed courses. If professor review data is available,
summarize the trend instead of dumping every review.
Be friendly and supportive, but avoid unnecessary small talk. Focus on giving
clear, actionable advice to help the student make informed decisions.

If the user asks for a schedule or what to take next, do not ask for their major first.
Assume they are a Computer Science student unless they say otherwise.
Use the student's year from GetStudentHistory when it is available.
If the student's year is not available, assume they are early junior level.
If they do not say how many courses they want, recommend 4 courses.
Use completed courses to suggest reasonable next courses from available mock data only.
Mention assumptions briefly, then give a concrete recommendation.
Do not recommend courses that are not present in the tool data.
Do not end by asking whether to check professor reviews. If professor data would help,
call ReviewsAgent yourself and include a short professor/section note in the answer.
Do not end with follow-up questions unless the user explicitly asks for options.

Use short paragraphs and bullet points for readability, especially when listing
courses, sections, prerequisites, or professor comparisons. Keep answers concise.

"""

# our chat function which is called by FastAPI when a user hits the /chat endpoint.
def chat(message: str, student_id: str = "demo-student") -> dict[str, Any]:
    """Called by FastAPI when the user sends a chat message."""

    # if we do not have an API key we give a nice error
    if not os.getenv("GOOGLE_API_KEY"):
        return {
            "reply": "Missing GOOGLE_API_KEY. Add it to your .env file, then restart the backend.",
            "model": MODEL_NAME,
            "used_tools": [],
            "trace": [],
        }

    trace: list[dict[str, Any]] = [] # keeps track of what the agents do for debugging

    # call the orchestrator agent, which will call sub-agents as needed
    reply, used_tools, model_used = run_gemini_agent(message, student_id, trace)
    # we expect to get back the reply, a list of tools used and the model used.

    # return the reply and other helpful stuff to the frontend when we are done. 
    return {
        "reply": reply,
        "model": model_used,
        "used_tools": used_tools,
        "trace": trace,
    }


# this is the function we called in chat that actually calls the gemini api for our orchestrator agent
def run_gemini_agent(
    message: str,
    student_id: str,
    trace: list[dict[str, Any]],
) -> tuple[str, list[str], str]: # will return the reply, list of tools and the model name
    
    """Send the user message to Gemini and let it call our sub-agent tools.
    We also log that the orchestrator started and what model we are using."""
    add_trace(
        trace,
        "orchestrator",
        "start",
        {"student_id": student_id, "message": message},
    )

    # import Gemini SDK pieces here so the app can still start if dependencies are missing
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        add_trace(trace, "orchestrator", "error", {"message": "Missing dependencies"})
        return (
            "Install dependencies with `pip install -r requirements.txt` to enable Gemini calls.",
            [],
            MODEL_NAME,
        )

    # initialize Gemini client and set up for tool calls
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    used_tools: list[str] = []
    model_used = MODEL_NAME
    add_trace(trace, "orchestrator", "model_selected", {"model": model_used})
    # log the model used in the trace

    '''  
        we pass a prompt in addition to our instructions to give the agent message-specific context.
        instructions are for the agent's general behavior
        the prompt is for this specific user message
    '''

    # This is where we actually give the user's question and student id
    prompt = (
        f"Student ID: {student_id}\n"
        f"User question: {message}\n\n"
        "Use EligibilityAgent for course/prerequisite/student-history questions. "
        "Use ReviewsAgent for professor review questions."
    )

    # set up the Gemini message content and config. This is where we pass in the tool schemas.
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])] 
    config = types.GenerateContentConfig(
        system_instruction=ORCHESTRATOR_INSTRUCTION,
        tools=[types.Tool(function_declarations=ORCHESTRATOR_TOOL_SCHEMAS)],
    )

    # THIS IS THE MAIN AGENT LOOP WHERE TOOL CALLING HAPPENS!
    # sample process: ask gemini -> call tool -> ask gemini -> call tool -> ask gemini -> get answer
    for _ in range(MAX_TOOL_ROUNDS): # see what tools Gemini wants to call, then call them
        try:
            add_trace(trace, "orchestrator", "llm_request", {"model": model_used})
            response = client.models.generate_content(
                model=model_used,
                contents=contents,
                config=config,
            )
        except Exception as error: # log any errors
            add_trace(trace, "orchestrator", "llm_error", {"error": str(error)})
            return (
                "Gemini returned an API error. Check that your `GOOGLE_API_KEY` is valid "
                f"and that `{model_used}` is available for your account. Details: {error}",
                used_tools,
                model_used,
            )

        # if there are function calls, call the requested tools
        function_calls = getattr(response, "function_calls", None) or []
        if not function_calls: # if no function calls required then we just return the response
            add_trace(trace, "orchestrator", "final_answer", {"used_tools": used_tools})
            return response_text(response), used_tools, model_used

        # Add Gemini's function-call request message to the conversation history.
        contents.append(response.candidates[0].content)
        tool_results = []
        add_trace( # add to trace 
            trace,
            "orchestrator",
            "tool_calls_requested",
            {"tools": [call.name for call in function_calls]},
        )

        # call all the sub-agent tools it wanted to use and get the results
        for call in function_calls:
            args = dict(call.args or {}) # get arguments from the function call request
            add_trace( 
                trace,
                "orchestrator",
                "tool_call_started",
                {"tool": call.name, "args": args},
            )

            tool_result = call_orchestrator_tool(call.name, args, student_id, trace)
            # route the function name and arguments to the right Python function

            used_tools.append(call.name) # log tools used
            for sub_tool in tool_result.get("used_tools", []):
                used_tools.append(f"{call.name}.{sub_tool}")
            add_trace(
                trace,
                "orchestrator",
                "tool_call_finished",
                {"tool": call.name, "status": tool_result.get("status")},
            )
            tool_results.append(
                types.Part.from_function_response(name=call.name, response=tool_result)
            )

        # now we can append the tool RESULTS to the contents and go back to top of loop
        contents.append(types.Content(role="tool", parts=tool_results))

    return (  # if we get here then too many tool calls so return message to user
        "Gemini kept asking for tools and did not produce a final answer. Try a more specific question.",
        used_tools,
        model_used,
    )




# that was the main orchestrator loop
# below this are helper functions

# this is the orchestrator's tool call handler
def call_orchestrator_tool(
    name: str,
    args: dict[str, Any],
    student_id: str,
    trace: list[dict[str, Any]],
) -> dict[str, Any]: # actually call the sub-agents here
    if name == "EligibilityAgent":
        return run_eligibility_agent(args["question"], student_id, trace)
    if name == "ReviewsAgent":
        return run_reviews_agent(args["question"], trace)

    return {"status": "error", "message": f"Unknown orchestrator tool: {name}"}


# helper function for adding a trace event
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


# helper function to extract text from gemini response
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


# these are the only tools the orchestrator agent sees.
# each one is really a sub-agent wrapped as a tool.
ORCHESTRATOR_TOOL_SCHEMAS = [
    {
        "name": "EligibilityAgent",
        "description": (
            "Ask the eligibility sub-agent about course info, sections, "
            "prerequisites, or a student's completed courses."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The course eligibility question to answer.",
                }
            },
            "required": ["question"],
        },
    },
    {
        "name": "ReviewsAgent",
        "description": "Ask the reviews sub-agent about professor review trends.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The professor review question to answer.",
                }
            },
            "required": ["question"],
        },
    },
]
