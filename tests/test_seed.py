import database
import seed

from engine import critical_path, load_graph, recalculate


def starts(conn):
    return {
        row["title"]: seed.day_number(row["start_date"])
        for row in conn.execute(
            "SELECT title, start_date FROM tasks"
        )
    }


def test_seed_creates_ten_tasks_and_twelve_links(db_path):
    seed.main()

    with database.db() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0] == 10

        assert conn.execute(
            "SELECT COUNT(*) FROM dependencies"
        ).fetchone()[0] == 12


def test_a_three_day_slip_moves_every_downstream_task_by_exactly_three(
    db_path,
):
    seed.main()

    with database.db() as conn:
        before = starts(conn)

        conn.execute(
            """
            UPDATE tasks
            SET duration_days = 6
            WHERE title = 'Gather requirements'
            """
        )

        recalculate(conn)
        after = starts(conn)

    unchanged = {
        "Project kickoff",
        "Gather requirements",
    }

    for title in before:
        expected = (
            0
            if title in unchanged
            else 3
        )

        assert after[title] - before[title] == expected


def test_the_seed_critical_path_skips_frontend_and_docs(
    db_path,
):
    seed.main()

    with database.db() as conn:
        tasks, edges = load_graph(conn)

        slack = {
            tasks[task_id]["title"]: days
            for task_id, days in critical_path(
                tasks,
                edges,
            ).items()
        }

    assert slack["Build frontend board"] == 1
    assert slack["Write user documentation"] == 3

    assert [
        title
        for title, days in slack.items()
        if days > 0
    ] == [
        "Build frontend board",
        "Write user documentation",
    ]