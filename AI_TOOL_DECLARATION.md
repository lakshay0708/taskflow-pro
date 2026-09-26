# AI-Tool Declaration

## 1. AI tools used during the build process

I used Claude (Anthropic's AI assistant) before the Build Sprint window opened, to put together a step-by-step build guide for this project - covering the data model, the graph engine, the API, the frontend, and the AI feature. I used this the same way I'd use a tutorial or a reference document: I read the reasoning behind each part, then wrote and ran the code myself during the actual sprint window (Sep 25-28).

I followed the guide's structure and code closely rather than rewriting it from scratch, so a fair way to describe this is: the explanations and reference code came from AI ahead of time, and typing, running, debugging and testing all of it was done by me during the sprint.

## 2. AI/LLM feature inside the product itself

- **Feature:** AI-assisted prerequisite suggestion (`ai_suggest.py`). When a new task is created, it suggests which existing tasks are likely prerequisites.
- **Model used:** Claude (`claude-haiku-4-5-20251001`) via the Anthropic API when `ANTHROPIC_API_KEY` is set. Falls back to a keyword-overlap heuristic (no external call) if there's no key, the network is down, or the response can't be parsed.
- **Reducing hallucination:** The prompt only lists real existing task titles and IDs and tells the model not to invent new ones. On top of that, the backend independently re-checks every suggestion - any ID that isn't a real task, is the new task itself, already exists as a dependency, or would create a cycle gets dropped before the user ever sees it.
- **Human stays in the loop:** The suggestion endpoint is read-only and never writes to the database. A suggestion only becomes a real dependency once the user ticks it and confirms, and it then goes through the same cycle check as a manually added one.

## 3. Human verification and testing

The implementation was written, run, debugged and tested locally during the Build Sprint.

Testing included:

- API testing through FastAPI/Swagger
- Browser testing of the Kanban board
- Drag-and-drop testing
- Dependency cycle rejection
- Blocked-task and rollback behavior
- Duration and schedule propagation
- AI suggestion approval and skip flows
- Keyword fallback testing
- Automated pytest testing

The final automated test suite contains 34 tests.
