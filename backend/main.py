from pathlib import Path
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.orchestrate import chat

'''
Don't need to code anything in here. It just sets up our backend with FastAPI and 
makes a couple endpoints we need. There is no agent logic in here but feel free to 
take a look around and add more endpoints in the future!
'''

# these are pydantic models for request validation and response formatting. 
# they make sure the output is in a structured format that the frontend can rely on
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    student_id: str = "demo-student"


class ChatResponse(BaseModel):
    reply: str
    model: str
    used_tools: list[str] = []

# create fastapi app
app = FastAPI(
    title="UTD Course Planner Assistant",
    description="Workshop demo API for agents, tools, and MCP.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# define API endpoints
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

# this is where we call the main chat function
@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> dict[str, Any]:
    return chat(message=request.message, student_id=request.student_id)


# mount the frontend static files for easier running of the demo
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
