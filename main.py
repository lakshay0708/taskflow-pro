from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ai_suggest
from database import COLUMNS, db, init_db
from engine import critical_path, recalculate
from graph import creates_cycle


app = FastAPI(title="TaskFlow Pro", version="1.0")

init_db()


class TaskIn(BaseModel):
    title: str
    description: str = ""
    duration_days: int = 1
    planned_start: Optional[str] = None


class StatusIn(BaseModel):
    status: str


class DependencyIn(BaseModel):
    task_id: int
    depends_on_id: int


class DurationIn(BaseModel):
    duration_days: int


class SuggestIn(BaseModel):
    task_id: int


def read_board(conn):
    tasks = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM tasks ORDER BY id"
        )
    ]

    dependencies = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM dependencies ORDER BY id"
        )
    ]

    slack = critical_path(
        {task["id"]: task for task in tasks},
        [
            (dep["task_id"], dep["depends_on_id"])
            for dep in dependencies
        ],
    )

    for task in tasks:
        task["slack_days"] = slack.get(task["id"], 0)
        task["is_critical"] = (
            1 if task["slack_days"] == 0 else 0
        )

    return {
        "columns": COLUMNS,
        "tasks": tasks,
        "dependencies": dependencies,
    }


def is_valid_date(text):
    try:
        year, month, day = (
            int(part)
            for part in str(text).split("-")
        )
        date(year, month, day)
        return True
    except (ValueError, TypeError):
        return False


def load_ids_and_edges(conn):
    task_ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM tasks"
        )
    ]

    edges = [
        (row["task_id"], row["depends_on_id"])
        for row in conn.execute(
            "SELECT task_id, depends_on_id FROM dependencies"
        )
    ]

    return task_ids, edges


@app.get("/api/board")
def get_board():
    with db() as conn:
        return read_board(conn)


@app.post("/api/tasks")
def create_task(payload: TaskIn):
    title = payload.title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Give the task a title.",
        )

    if payload.duration_days < 1:
        raise HTTPException(
            status_code=400,
            detail="Duration must be at least 1 day.",
        )

    planned_start = (
        payload.planned_start
        or date.today().isoformat()
    )

    if not is_valid_date(planned_start):
        raise HTTPException(
            status_code=400,
            detail="Start date must look like 2026-01-31.",
        )

    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks
            (title, description, status, planned_start, duration_days)
            VALUES (?, ?, 'Backlog', ?, ?)
            """,
            (
                title,
                payload.description.strip(),
                planned_start,
                payload.duration_days,
            ),
        )

        new_id = cursor.lastrowid

        recalculate(conn)

        return {
            "created_id": new_id,
            "board": read_board(conn),
        }


@app.patch("/api/tasks/{task_id}/status")
def move_task(task_id: int, payload: StatusIn):
    if payload.status not in COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unknown column '%s'. Use one of: %s"
                % (
                    payload.status,
                    ", ".join(COLUMNS),
                )
            ),
        )

    with db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="That task does not exist.",
            )

        current = (
            COLUMNS.index(row["status"])
            if row["status"] in COLUMNS
            else 0
        )

        target = COLUMNS.index(payload.status)

        if row["is_blocked"] == 1 and target > current:
            raise HTTPException(
                status_code=409,
                detail=(
                    "'%s' is blocked: finish its prerequisites first."
                    % row["title"]
                ),
            )

        conn.execute(
            "UPDATE tasks SET status = ? WHERE id = ?",
            (payload.status, task_id),
        )

        recalculate(conn)

        return {"board": read_board(conn)}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="That task does not exist.",
            )

        conn.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,),
        )

        recalculate(conn)

        return {"board": read_board(conn)}


@app.post("/api/dependencies")
def add_dependency(payload: DependencyIn):
    with db() as conn:
        task_ids, edges = load_ids_and_edges(conn)

        if (
            payload.task_id not in task_ids
            or payload.depends_on_id not in task_ids
        ):
            raise HTTPException(
                status_code=404,
                detail="One of those tasks does not exist.",
            )

        if payload.task_id == payload.depends_on_id:
            raise HTTPException(
                status_code=409,
                detail="A task cannot depend on itself.",
            )

        if (
            payload.task_id,
            payload.depends_on_id,
        ) in edges:
            raise HTTPException(
                status_code=409,
                detail="That dependency already exists.",
            )

        if creates_cycle(
            task_ids,
            edges,
            (
                payload.task_id,
                payload.depends_on_id,
            ),
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Rejected: that would create a circular "
                    "dependency. The board is unchanged."
                ),
            )

        conn.execute(
            """
            INSERT INTO dependencies
            (task_id, depends_on_id)
            VALUES (?, ?)
            """,
            (
                payload.task_id,
                payload.depends_on_id,
            ),
        )

        recalculate(conn)

        return {"board": read_board(conn)}


@app.delete("/api/dependencies/{dependency_id}")
def remove_dependency(dependency_id: int):
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM dependencies WHERE id = ?",
            (dependency_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="That dependency does not exist.",
            )

        conn.execute(
            "DELETE FROM dependencies WHERE id = ?",
            (dependency_id,),
        )

        recalculate(conn)

        return {"board": read_board(conn)}


@app.patch("/api/tasks/{task_id}/duration")
def change_duration(task_id: int, payload: DurationIn):
    if payload.duration_days < 1:
        raise HTTPException(
            status_code=400,
            detail="Duration must be at least 1 day.",
        )

    if payload.duration_days > 365:
        raise HTTPException(
            status_code=400,
            detail="Duration must be 365 days or fewer.",
        )

    with db() as conn:
        row = conn.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="That task does not exist.",
            )

        conn.execute(
            """
            UPDATE tasks
            SET duration_days = ?
            WHERE id = ?
            """,
            (
                payload.duration_days,
                task_id,
            ),
        )

        recalculate(conn)

        return {"board": read_board(conn)}


def ground_suggestions(
    raw,
    tasks,
    task_ids,
    edges,
    new_task_id,
):
    grounded = []
    seen = set()
    existing = set(edges)

    for item in raw:
        if not isinstance(item, dict):
            continue

        candidate_id = item.get("id")

        if (
            isinstance(candidate_id, str)
            and candidate_id.strip().isdigit()
        ):
            candidate_id = int(candidate_id.strip())

        if not isinstance(candidate_id, int):
            continue

        if candidate_id in seen:
            continue

        if candidate_id == new_task_id:
            continue

        if candidate_id not in tasks:
            continue

        if (new_task_id, candidate_id) in existing:
            continue

        if creates_cycle(
            task_ids,
            edges,
            (new_task_id, candidate_id),
        ):
            continue

        reason = item.get("reason")

        if not isinstance(reason, str):
            reason = ""

        seen.add(candidate_id)

        grounded.append(
            {
                "id": candidate_id,
                "title": tasks[candidate_id]["title"],
                "reason": reason.strip()[:120],
            }
        )

        if len(grounded) >= ai_suggest.MAX_SUGGESTIONS:
            break

    return grounded


@app.post("/api/suggestions")
def suggest_prerequisites(payload: SuggestIn):
    with db() as conn:
        tasks = {
            row["id"]: dict(row)
            for row in conn.execute(
                "SELECT * FROM tasks"
            )
        }

        task_ids, edges = load_ids_and_edges(conn)

        if payload.task_id not in tasks:
            raise HTTPException(
                status_code=404,
                detail="That task does not exist.",
            )

        new_task = tasks[payload.task_id]
        already_linked = set(edges)

        candidates = [
            task
            for task in tasks.values()
            if (
                task["id"] != payload.task_id
                and (
                    payload.task_id,
                    task["id"],
                ) not in already_linked
            )
        ]

        if not candidates:
            return {
                "source": "none",
                "requires_approval": True,
                "suggestions": [],
            }

        source = "keyword"
        raw = []

        reply = ai_suggest.call_llm(
            ai_suggest.build_prompt(
                new_task,
                candidates,
            )
        )

        if reply:
            parsed = ai_suggest.extract_json(reply)

            if (
                isinstance(parsed, dict)
                and isinstance(
                    parsed.get("suggestions"),
                    list,
                )
            ):
                raw = parsed["suggestions"]
                source = "llm"

        grounded = ground_suggestions(
            raw,
            tasks,
            task_ids,
            edges,
            payload.task_id,
        )

        if not grounded:
            raw = ai_suggest.keyword_suggestions(
                new_task,
                candidates,
            )

            grounded = ground_suggestions(
                raw,
                tasks,
                task_ids,
                edges,
                payload.task_id,
            )

            source = "keyword"

        return {
            "source": source,
            "requires_approval": True,
            "suggestions": grounded,
        }


STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    app.mount(
        "/",
        StaticFiles(
            directory=str(STATIC_DIR),
            html=True,
        ),
        name="static",
    )