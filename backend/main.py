from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.orchestrate import chat, get_tool_schemas


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    student_id: str = "demo-student"


class ChatResponse(BaseModel):
    reply: str
    model: str
    used_tools: list[str] = []


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


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> dict[str, Any]:
    return chat(message=request.message, student_id=request.student_id)


@app.get("/tools")
def tool_schemas() -> list[dict]:
    return get_tool_schemas()


# mount the frontend static files for easier runnin of the demo
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
