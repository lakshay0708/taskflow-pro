from datetime import date, timedelta

from graph import build_indexes, topological_sort

DONE = "Done"


def parse_date(text):
    year, month, day = (int(part) for part in text.split("-"))
    return date(year, month, day)


def format_date(value):
    return value.isoformat()


def load_graph(conn):
    tasks = {
        row["id"]: dict(row)
        for row in conn.execute("SELECT * FROM tasks ORDER BY id")
    }

    edges = [
        (row["task_id"], row["depends_on_id"])
        for row in conn.execute(
            "SELECT task_id, depends_on_id FROM dependencies"
        )
    ]

    return tasks, edges


def recalculate(conn):
    tasks, edges = load_graph(conn)
    task_ids = list(tasks.keys())

    order = topological_sort(task_ids, edges)

    if order is None:
        raise RuntimeError(
            "The saved graph contains a cycle and cannot be scheduled."
        )

    prereqs, dependents, indegree = build_indexes(task_ids, edges)

    for task_id in order:
        task = tasks[task_id]
        my_prereqs = prereqs[task_id]

        start = parse_date(task["planned_start"])

        if my_prereqs:
            start = max(
                start,
                max(
                    parse_date(tasks[p]["end_date"])
                    for p in my_prereqs
                )
            )

        end = start + timedelta(
            days=int(task["duration_days"])
        )

        task["start_date"] = format_date(start)
        task["end_date"] = format_date(end)

        blocked = any(
            tasks[p]["status"] != DONE
            or tasks[p]["is_blocked"] == 1
            for p in my_prereqs
        )

        task["is_blocked"] = 1 if blocked else 0

    for task_id, task in tasks.items():
        conn.execute(
            """
            UPDATE tasks
            SET start_date = ?, end_date = ?, is_blocked = ?
            WHERE id = ?
            """,
            (
                task["start_date"],
                task["end_date"],
                task["is_blocked"],
                task_id,
            ),
        )

    return tasks


def critical_path(tasks, edges):
    if not tasks:
        return {}

    task_ids = list(tasks.keys())

    order = topological_sort(task_ids, edges)

    if order is None:
        return {}

    prereqs, dependents, indegree = build_indexes(
        task_ids,
        edges
    )

    project_end = max(
        parse_date(task["end_date"])
        for task in tasks.values()
    )

    latest_finish = {}

    for task_id in reversed(order):
        waiting = dependents[task_id]

        if not waiting:
            latest_finish[task_id] = project_end
        else:
            latest_finish[task_id] = min(
                latest_finish[d]
                - timedelta(
                    days=int(tasks[d]["duration_days"])
                )
                for d in waiting
            )

    return {
        task_id: (
            latest_finish[task_id]
            - parse_date(tasks[task_id]["end_date"])
        ).days
        for task_id in task_ids
    }