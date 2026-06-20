# Agents, Tools, MCP Workshop

This repo contains a small UTD course planner assistant implemented with an AI agent with tool use and MCP. 

This demo keeps the architecture very simple:

- FastAPI exposes a `/chat` endpoint.
- `backend/orchestrate.py` defines the top-level Gemini orchestrator agent, simulated memory, and chat function.
- `backend/subagents.py` defines the eligibility and reviews sub-agents.
- `backend/data_tools.py` defines the mock JSON-backed tool functions and tool schemas.
- Vanilla HTML/CSS/JS provides a tiny chat UI.
- Mock JSON data stands in for future database-backed implementations.

## what are all these files???

```text
backend/
  main.py                  FastAPI app, request/response models, endpoints
  orchestrate.py           Orchestrator agent, memory, chat entrypoint
  subagents.py             Eligibility and reviews sub-agents
  data_tools.py            JSON-backed tools and tool schemas
  data/
    courses.json           Mock course and section data
    rmp_reviews.json       Mock Rate My Professors-style data
    students.json          Mock completed course data
frontend/
  index.html               Vanilla UI
  styles.css               UI styling
  app.js                   Calls FastAPI chat endpoint
requirements.txt           Python dependencies
```

## Run Locally

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Then open `http://localhost:8000` in your browser. The same FastAPI server serves everything. 

Go to `http://localhost:8000`/docs to see nice interative documentation of the endpoints you have. 

## API Keys

For the first working agent loop, students only need a Gemini API key:

1. Install Python 3.10 or later.
2. Install dependencies with `pip install -r requirements.txt` if not in a codespace
3. Create a Gemini API key in Google AI Studio.
4. Make a .env file in the root of the project, meaning it should not be in any folder
5. Copy `.env.example` to `.env`
6. Replace `YOUR_GOOGLE_AI_STUDIO_KEY` with the real key.
7. Make sure the model is: `GEMINI_MODEL="gemini-2.0-flash"`
8. Start the app with `uvicorn backend.main:app --reload`

For a later MCP iteration:

1. Create a Brave Search API key.
2. Install/configure the Brave Search MCP server.
3. Replace the mock `GetRMPScore` body in `backend/data_tools.py` with a Brave MCP search call.
4. Return raw review snippets to Gemini so the agent can summarize them.

## Summary

With no buzzwords, all this really boils down to is giving an LLM access to tools it can ask you for. The LLM decides which tool(s) it needs to complete its tasks and tells you. You have to handle this and call the correct tool function (which you implemented). Then you give the results from that function call back to the LLM which uses it to either give an output or call another tool.

This is known as the agent loop.

We strongly encourage you to keep building so here are some suggestions for future improvements for this specific project:

- a real database for courses and student histories rather than hardcoded json
- Brave Search MCP for Rate My Professors lookup
- ADK sessions/memory instead of the current list-based simulated memory
- Implementing multiple agents for more use cases.
