# AgentsToolsMCP

HackUTD Fall 2026 workshop on agents, tools, and MCP.

This repo contains a small UTD course planner assistant scaffold for beginner to intermediate CS students preparing for a hackathon.

The demo intentionally keeps the architecture simple:

- FastAPI exposes a `/chat` endpoint.
- `backend/orchestrate.py` defines the Gemini Flash agent, simulated memory, tool schemas, tool functions, and chat function.
- Vanilla HTML/CSS/JS provides a tiny chat UI.
- Mock JSON data stands in for future database-backed implementations.

## Project Layout

```text
backend/
  main.py                  FastAPI app, request/response models, endpoints
  orchestrate.py           Agent, tool functions, schemas, memory, chat entrypoint
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

Then open `http://localhost:8000` in your browser. The same FastAPI server serves both the API and the vanilla frontend.

Useful endpoints:

- `GET /` - chat UI
- `GET /health` - simple API health check
- `GET /tools` - tool schemas exposed for the workshop
- `POST /chat` - chat endpoint used by the frontend

You can inspect the ADK-style `root_agent` definition near the bottom of `backend/orchestrate.py`.

## API Keys

For the first working agent loop, students only need a Gemini API key:

1. Install Python 3.10 or later.
2. Install dependencies with `pip install -r requirements.txt`.
3. Create a Gemini API key in Google AI Studio.
4. Copy `.env.example` to `.env`.
5. Replace `YOUR_GOOGLE_AI_STUDIO_KEY` with the real key.
6. Leave `GEMINI_MODEL="gemini-flash-latest"` unless you want to test a specific Gemini model.
7. Start the app with `uvicorn backend.main:app --reload`.

Without `GOOGLE_API_KEY`, `/chat` returns a setup message. This version expects students to use the real Gemini loop during the workshop.

For a later MCP iteration:

1. Create a Brave Search API key.
2. Install/configure the Brave Search MCP server.
3. Replace the mock `GetRMP` body in `backend/orchestrate.py` with a Brave MCP search call.
4. Return raw review snippets to Gemini so the agent can summarize them.

## Workshop Notes

The first iteration uses hard-coded mock data and a simple explicit tool loop. Future iterations can replace these with:

- a real database for courses and student histories
- Brave Search MCP for Rate My Professors lookup
- ADK sessions/memory instead of the current list-based simulated memory
