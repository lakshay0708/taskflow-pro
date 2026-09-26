# TaskFlow Pro

A dependency-aware Kanban board backed by a task dependency graph.

TaskFlow Pro combines a Kanban board with dependency-aware scheduling. Tasks move through four columns:

**Backlog → In Progress → Review → Done**

A dependency means:

**Task B cannot start until Task A finishes.**

The application keeps the task schedule, blocking state, dependency graph, rollback behavior, and critical-path information consistent after changes.

Built for a hackathon by **Lakshay Kumar Agarwal**.

---

## Running it

### 1. Create a virtual environment

On Windows:

```powershell
python -m venv venv
```

Activate it:

```powershell
venv\Scripts\activate
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Create the demo project

```powershell
python seed.py
```

This creates **10 sample tasks and 12 dependencies**, including converging dependency paths used to demonstrate the no-compounding rule and critical-path behavior.

### 4. Start the application

```powershell
uvicorn main:app --reload
```

Open the application at:

**http://127.0.0.1:8000/**

### 5. Run the test suite

```powershell
python -m pytest
```

The project contains **34 automated tests**.

---

## Features

### Dependency-aware scheduling

Tasks can depend on one or more prerequisite tasks.

The schedule is recalculated whenever task status, duration, or dependencies change.

A dependent task starts based on its planned start date and the completion dates of its direct prerequisites.

### Cycle prevention

The application rejects dependency links that would create a circular dependency.

For example, if:

```text
A depends on B
B depends on C
```

then creating:

```text
C depends on A
```

is rejected.

The existing dependency graph remains unchanged when the cycle is rejected.

### Blocking and rollback

A task cannot move forward while one of its prerequisites is unfinished.

When a completed prerequisite is moved backward, its dependent tasks become blocked again.

Blocked tasks keep their current Kanban column. They are flagged as blocked rather than being moved automatically.

### No-compounding delays

When the same downstream task can be reached through multiple dependency paths, a delay is counted only once.

For example:

```text
Requirements → Database → Backend
Requirements → API Design → Backend
```

If Requirements becomes three days longer, Backend moves by exactly three days rather than six.

### Critical path and slack

Each task displays either:

- `Critical path`
- or its available `Slack` in days

This makes it possible to identify which tasks currently determine the project finish date.

### Duration changes

Task duration can be increased or decreased directly from the board.

Changing an upstream duration automatically recalculates downstream schedules.

### AI prerequisite suggestions

When a new task is created, TaskFlow Pro can ask an LLM to suggest likely prerequisite tasks from the existing task list.

The AI does not create dependencies automatically.

Suggestions are shown to the user first, and a dependency is created only after the user selects and approves the suggestion.

### AI grounding

The AI can only suggest tasks from the real task catalog supplied to it.

The backend validates every returned task ID before accepting it.

Invalid IDs, malformed suggestions, self-references, existing dependencies, duplicate suggestions, and suggestions that would create a cycle are discarded.

### Non-AI fallback

The AI feature has a fallback.

When:

- no API key is available
- the API request fails
- the request times out
- the response cannot be parsed
- or the AI returns unusable suggestions

the application uses a deterministic keyword-based matcher instead.

The interface tells the user whether suggestions came from the LLM or from the fallback.

### Persistence

Tasks and dependencies are stored in SQLite.

Refreshing the page does not remove the current project state.

### Automated testing

The project contains 34 automated pytest tests covering:

- graph behavior
- scheduling
- rollback
- critical path
- API behavior
- seed data
- AI suggestion grounding
- keyword fallback

---

## Key Assumptions

1. A task's start date is the later of its planned start date and the latest end date among its direct prerequisites.

2. `end_date = start_date + duration_days`, using calendar days.

3. A dependent task starts on the same calendar day its prerequisite ends. That day is treated as a handoff, so there is no additional one-day gap.

4. Only `Done` counts as finished. A task in `Review` still blocks its dependents.

5. Blocking never changes a task's Kanban column. A blocked task may remain where it is or move backward, but it cannot move forward.

6. Dependencies are finish-to-start relationships only. There are no start-to-start relationships, lag values, or lead values.

7. Deleting a task deletes every dependency connected to that task.

8. Slack is measured against the latest end date of any task on the board.

9. The application is designed for a single user and does not provide authentication or multi-user conflict handling.

10. AI suggestions are advisory. The AI model never writes directly to the database.

---

## Limitations

1. There is no working-calendar system. Weekends and public holidays are treated as normal calendar days.

2. There is no authentication or multi-user support. Simultaneous users are not handled with conflict resolution.

3. Drag-and-drop uses browser pointer-based drag-and-drop. The Back and Forward buttons provide an alternative way to move tasks.

4. There is no undo for deleted tasks or dependencies.

5. The board is fully redrawn after every change. This is suitable for a small task board but would need optimization for a much larger number of tasks.

6. Dates are displayed on cards without the year, although the stored dates use the full ISO date format.

7. The keyword fallback is a small English-language heuristic based on word overlap and may miss dependencies described with unusual vocabulary.

8. After a task is created, the frontend exposes duration as the editable scheduling property.

9. The critical path is displayed as labels on task cards rather than as a separate network diagram or Gantt chart.

10. Automated tests call endpoint functions directly rather than driving a browser. Browser behavior is covered by the manual end-to-end testing process.

---

## Testing

Run the complete test suite with:

```powershell
python -m pytest
```

Expected result:

```text
34 passed
```

### Test coverage

| Test file | What it proves |
|---|---|
| `tests/test_graph.py` | Topological ordering, cycle detection, and graph safety |
| `tests/test_engine.py` | Scheduling, direct prerequisites, no-compounding delays, rollback, recovery, and critical path |
| `tests/test_api.py` | API validation, cycle rejection, blocked moves, duration updates, deletion, and persistence |
| `tests/test_seed.py` | 10 demo tasks, 12 dependency links, three-day delay propagation, and expected critical-path behavior |
| `tests/test_grounding.py` | Invalid AI suggestions, malformed suggestions, self-references, cycle-forming suggestions, and keyword fallback |

Each automated test uses its own temporary SQLite database so the test suite does not modify the normal `taskflow.db`.

---

## Security

- API credentials are stored locally in `.env` and are excluded from Git using `.gitignore`.
- `.env.example` contains only an empty placeholder and never contains a real API key.
- SQL queries use parameterized `?` placeholders.
- Frontend user input is inserted with `textContent` rather than `innerHTML`.
- The application serves the frontend and API from the same origin.

---

## AI prerequisite suggestion flow

When a user creates a new task:

1. The new task title and notes are collected.
2. The existing task catalog is provided to the AI model.
3. The model is instructed to select only from the provided task IDs.
4. The response is parsed as JSON.
5. `ground_suggestions()` validates the returned suggestions.
6. Invalid, malformed, self-referencing, duplicate, already-existing, or cycle-forming suggestions are removed.
7. Valid suggestions are displayed to the user.
8. The user chooses which suggestions to approve.
9. Approved suggestions are added through the normal dependency endpoint.
10. The same cycle checks and database validation are applied before the dependency is stored.
11. If the LLM is unavailable, the deterministic keyword fallback is used instead.

---

## Demo workflow

The easiest way to create the demo board is:

```powershell
python seed.py
```

Then start the server:

```powershell
uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

The seeded project demonstrates:

- task dependencies
- blocked tasks
- converging dependency paths
- schedule propagation
- critical-path tasks
- slack
- rollback behavior
- cycle prevention
- persistence

---

## Project layout

```text
taskflow-pro/
│
├── main.py
├── database.py
├── graph.py
├── engine.py
├── ai_suggest.py
├── seed.py
├── check_no_compounding.py
├── requirements.txt
├── pytest.ini
├── README.md
├── AI_TOOL_DECLARATION.md
├── .gitignore
├── .env.example
│
├── tests/
│   ├── conftest.py
│   ├── test_graph.py
│   ├── test_engine.py
│   ├── test_api.py
│   ├── test_seed.py
│   └── test_grounding.py
│
└── static/
    ├── index.html
    ├── style.css
    └── app.js
```

### File responsibilities

| File | Purpose |
|---|---|
| `main.py` | FastAPI application, API endpoints, validation, and static-file serving |
| `database.py` | SQLite connection, schema, and database initialization |
| `graph.py` | Topological sorting, dependency indexing, and cycle detection |
| `engine.py` | Scheduling, blocking, rollback behavior, and critical-path calculation |
| `ai_suggest.py` | LLM request handling, JSON parsing, and keyword fallback |
| `seed.py` | Creates the 10-task demonstration project |
| `check_no_compounding.py` | Demonstrates that delays do not compound across converging paths |
| `requirements.txt` | Python dependencies |
| `pytest.ini` | Pytest configuration |
| `tests/` | Automated tests |
| `static/index.html` | Frontend structure |
| `static/style.css` | Frontend styling |
| `static/app.js` | Frontend interactions, drag-and-drop, API calls, and AI suggestion approval |

---

## API overview

### Board

```text
GET /api/board
```

Returns the current Kanban board, tasks, dependencies, critical-path values, and blocking state.

### Create a task

```text
POST /api/tasks
```

Creates a new task and recalculates its schedule.

### Move a task

```text
PATCH /api/tasks/{task_id}/status
```

Changes the task's Kanban status.

Blocked tasks cannot move forward.

### Delete a task

```text
DELETE /api/tasks/{task_id}
```

Deletes the task and its associated dependency links.

### Add a dependency

```text
POST /api/dependencies
```

Creates a `cannot start until` relationship after validating the graph.

### Remove a dependency

```text
DELETE /api/dependencies/{dependency_id}
```

Removes an existing dependency.

### Change duration

```text
PATCH /api/tasks/{task_id}/duration
```

Changes the task duration and recalculates dependent schedules.

### AI prerequisite suggestions

```text
POST /api/suggestions
```

Returns grounded prerequisite suggestions without directly creating dependencies.

---

## Environment configuration

Create a local `.env` file only when using the LLM feature.

The repository contains:

```text
.env.example
```

with:

```text
ANTHROPIC_API_KEY=
```

The actual `.env` file is ignored by Git and must never be committed.

The AI feature remains functional through the keyword fallback even when no API key is available.

---

## Repository safety

The following local/generated files are intentionally excluded from Git:

```text
.env
venv/
.venv/
__pycache__/
*.pyc
.pytest_cache/
taskflow.db
*.db
```

These files are recreated locally when needed and are not part of the submission.

---

## Author

**Lakshay Kumar Agarwal**

TaskFlow Pro was developed as a hackathon project demonstrating dependency-aware project scheduling, graph-based task management, automated validation, and AI-assisted prerequisite suggestions with a deterministic fallback.

<img width="3546" height="7113" alt="diagram (2)" src="https://github.com/user-attachments/assets/f2751c6f-77b3-407f-8d68-2c42397da7c0" />
