from datetime import date, timedelta

from database import DB_PATH, db, init_db
from engine import critical_path, load_graph, recalculate


PROJECT_START = date.today()

TASKS = [
    ("kickoff", "Project kickoff", "Agree scope, roles and the definition of done.", "Done", 0, 1),
    ("requirements", "Gather requirements", "Interview stakeholders and write the feature list.", "Done", 0, 3),
    ("schema", "Design database schema", "Tables, columns and relationships.", "In Progress", 0, 2),
    ("api_design", "Design API contract", "Agree every endpoint, its input and its output.", "Review", 0, 2),
    ("backend", "Build backend service", "Implement the endpoints agreed in the contract.", "Backlog", 0, 5),
    ("frontend", "Build frontend board", "The Kanban board users actually click on.", "Backlog", 0, 4),
    ("integration", "Integration testing", "Run the frontend against the real backend.", "Backlog", 0, 3),
    ("docs", "Write user documentation", "Setup guide and a walkthrough of the main flows.", "Backlog", 0, 2),
    ("uat", "User acceptance testing", "Five real users attempt five real scenarios.", "Backlog", 0, 2),
    ("deploy", "Deploy to production", "Ship it and watch the logs.", "Backlog", 0, 1),
]

DEPENDENCIES = [
    ("requirements", "kickoff"),
    ("schema", "requirements"),
    ("api_design", "requirements"),
    ("backend", "schema"),
    ("backend", "api_design"),
    ("frontend", "api_design"),
    ("integration", "backend"),
    ("integration", "frontend"),
    ("docs", "backend"),
    ("uat", "integration"),
    ("deploy", "uat"),
    ("deploy", "docs"),
]


def day_number(text):
    year, month, day = (
        int(part)
        for part in text.split("-")
    )

    return (date(year, month, day) - PROJECT_START).days


def main():
    init_db()

    with db() as conn:
        conn.execute("DELETE FROM dependencies")
        conn.execute("DELETE FROM tasks")

        exists = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'sqlite_sequence'
            """
        ).fetchone()

        if exists:
            conn.execute(
                """
                DELETE FROM sqlite_sequence
                WHERE name IN ('tasks', 'dependencies')
                """
            )

        ids = {}

        for key, title, description, status, offset, duration in TASKS:
            planned = (
                PROJECT_START + timedelta(days=offset)
            ).isoformat()

            cursor = conn.execute(
                """
                INSERT INTO tasks
                (title, description, status, planned_start, duration_days)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    title,
                    description,
                    status,
                    planned,
                    duration,
                ),
            )

            ids[key] = cursor.lastrowid

        for child_key, parent_key in DEPENDENCIES:
            conn.execute(
                """
                INSERT INTO dependencies
                (task_id, depends_on_id)
                VALUES (?, ?)
                """,
                (
                    ids[child_key],
                    ids[parent_key],
                ),
            )

        recalculate(conn)

        tasks, edges = load_graph(conn)
        slack = critical_path(tasks, edges)

        print(
            "Seeded %d tasks and %d dependencies into %s\n"
            % (
                len(TASKS),
                len(DEPENDENCIES),
                DB_PATH,
            )
        )

        print("id task status starts ends blocked slack")
        print(
            "--- -------------------------- "
            "------------- -------- -------- ------- -----"
        )

        for row in conn.execute(
            "SELECT * FROM tasks ORDER BY id"
        ):
            print(
                "%-3d %-26s %-13s day %-4d day %-4d %-7s %d"
                % (
                    row["id"],
                    row["title"],
                    row["status"],
                    day_number(row["start_date"]),
                    day_number(row["end_date"]),
                    "yes" if row["is_blocked"] else "no",
                    slack[row["id"]],
                )
            )

        print("\nConverging paths to check:")
        print(
            " Gather requirements -> Design database schema "
            "-> Build backend service"
        )
        print(
            " Gather requirements -> Design API contract "
            "-> Build backend service"
        )

        critical = sum(
            1
            for days in slack.values()
            if days == 0
        )

        print(
            "\nCritical path: %d of %d tasks have slack 0."
            % (
                critical,
                len(slack),
            )
        )


if __name__ == "__main__":
    main()
    