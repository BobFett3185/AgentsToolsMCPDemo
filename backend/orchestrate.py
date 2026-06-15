import os
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv() # needed to get API keys from our .env file

# Grab our model from .env, and point to the folder with our mock JSON data.
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
DATA_DIR = Path(__file__).resolve().parent / "data"
MAX_TOOL_ROUNDS = 5 # max number of tool-calling rounds before we stop

# Instructions for agent -- feel free to edit this to change the agent's behavior.
SYSTEM_INSTRUCTION = """
You are a UTD course planner assistant for hackathon workshop demos.
Help students reason about courses, prerequisites, sections, professors,
and schedule tradeoffs. Use tools when course data, professor reviews, or
student history would help answer the question.

Be concise and practical. If prerequisite data is available, compare it with
the student's completed courses. If professor review data is available,
summarize the trend instead of dumping every review.
Be friendly and supportive, but avoid unnecessary small talk. Focus on giving
clear, actionable advice to help the student make informed decisions.

Use short paragraphs and bullet points for readability, especially when listing
courses, sections, prerequisites, or professor comparisons. Keep answers concise.

"""

# Tiny simulated memory. A database can replace this later.
memory: list[dict[str, str]] = []

# our chat function which is called by FastAPI when a user hits the /chat endpoint. 
def chat(message: str, student_id: str = "demo-student") -> dict[str, Any]:
    """Called by FastAPI when the user sends a chat message."""

    # Save the user message in our simple memory list. Right now this is for demo/debugging;
    # we are not sending full memory back to Gemini yet.
    memory.append({"role": "user", "content": message})

    # if we do not have an API key we give a nice error 
    if not os.getenv("GOOGLE_API_KEY"):
        return {
            "reply": "Missing GOOGLE_API_KEY. Add it to your .env file, then restart the backend.",
            "model": MODEL_NAME,
            "used_tools": [],
        }

    reply, used_tools = run_gemini_agent(message, student_id)
    # run_gemini_agent handles any tool calls internally and returns the final text reply.

    # Save the assistant reply too. Later, we could pass memory into the prompt for real chat history.
    memory.append({"role": "assistant", "content": reply})

    # return stuff to the frontend
    return {"reply": reply, "model": MODEL_NAME, "used_tools": used_tools}


# this is the function we called in chat that actually calls the gemini api
def run_gemini_agent(message: str, student_id: str) -> tuple[str, list[str]]:
    """Send the user message to Gemini and let it call our tools.
    we return the plain text reply for the chatbot and a list of tools called for debugging"""
    
    # import needed libraries
    # if you are in your own env then run: "pip install -r requirements.txt"
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return (
            "Install dependencies with `pip install -r requirements.txt` to enable Gemini calls.",
            [],
        )

    # initialize gemini client and set up for tool calls
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    used_tools: list[str] = []

    # we pass a prompt in addition to our instructions that gives our agent more context.
    #  This is where we actually give the user's question and student id
    prompt = (
        f"Student ID: {student_id}\n"
        f"User question: {message}\n\n"
        "Use the tools when they help. For prerequisite questions, call "
        "GetPrevClasses and GetCourseInfo."
    )

    # we set up the content and config for our gemini call. This is where we pass in the tool schemas
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])] # give it the prompt
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION, # give it the instructions
        tools=[types.Tool(function_declarations=TOOL_SCHEMAS)], # give it the tools
    )

    #contents = individual message varying by user and their question 
    # config = given to agent regarding tools and instructions. Consistent across users and questions

    #THIS IS THE MAIN AGENT LOOP WHERE TOOL CALLING HAPPENS!
    #sample process: ask gemini -> call tool -> ask gemini -> call tool -> ask gemini -> get answer 

    # probably important for the hackers to do this part? 
    # have them do this as well as implementing the actual tools


    # we let the agent run up to MAX_TOOL_ROUNDS(5) tool-calling rounds.
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = client.models.generate_content( # get a response
                model=MODEL_NAME,
                contents=contents,
                config=config,
            )

        except Exception as error: # Give a nice error message if api call fails
            return (
                "Gemini returned an API error. Check that your `GOOGLE_API_KEY` is valid "
                f"and that `{MODEL_NAME}` is available for your account. Details: {error}",
                used_tools,
            )

        # grab the function calls in this array
        function_calls = getattr(response, "function_calls", None) or []
        if not function_calls: # if gemini don't wanna use tools
            return response_text(response), used_tools # we return from the function with a text reply and tools used

        # Add Gemini's function-call request message to the conversation history.
        contents.append(response.candidates[0].content)
        tool_results = []

        # call all the tools it wanted to use and get the results
        for call in function_calls:
            tool_result = call_tool(call.name, dict(call.args or {}))
            used_tools.append(call.name)
            tool_results.append(
                types.Part.from_function_response(name=call.name, response=tool_result)
            )

        # now we can append the tool RESULTS to the contents
        contents.append(
            types.Content(
                role="tool",
                parts=tool_results,
            )
        )

    # we either return before here or give this message after 5 tool rounds
    return (
        "Gemini kept asking for tools and did not produce a final answer. Try a more specific question.",
        used_tools,
    )



# these are the functions that implement our tools. In a real app these could call databases instead 
# its important to note that these have to be actually called by our code, not the agent 
# the agent tells us which tool to call and we call these functions

# they are all pretty simple and similar just load and return data from a json 

# get course info tool 
def get_course_info(courseNumber: str) -> dict[str, Any]:
    """Return course metadata and all sections for a courseNumber like CS 3345."""
    courses = load_json("courses.json")
    course_number = courseNumber.strip().upper()
    course = courses.get(course_number)

    if course is None:
        return {"status": "not_found", "courseNumber": course_number}

    return {"status": "success", "courseNumber": course_number, **course}



# get previous classes tool
def get_prev_classes(studentID: str) -> dict[str, Any]:
    """Return a student's completed courses."""
    students = load_json("students.json")
    student = students.get(studentID)

    if student is None:
        return {"status": "not_found", "studentID": studentID}

    return {"status": "success", "studentID": studentID, **student}



#get rate my professor reviews tool
# this can be replaced by the web search mcp 

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



# this is our tool call handler that we call to use tools
def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "GetCourseInfo":
        return get_course_info(args["courseNumber"])
    if name == "GetPrevClasses":
        return get_prev_classes(args["studentID"])
    if name == "GetRMP":
        return get_rmp(args["professor"], args["course"])

    return {"status": "error", "message": f"Unknown tool: {name}"}



# helper function to load mock data
def load_json(file_name: str) -> dict[str, Any]:
    with (DATA_DIR / file_name).open(encoding="utf-8") as file:
        return json.load(file)



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



# these are our tool schemas in the format gemini can understand
# we pass this information to the gemini agent so it knows what tools it has and how to call them


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
