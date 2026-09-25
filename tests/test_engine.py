from engine import critical_path, load_graph, recalculate


def build(conn, tasks, links):
    ids = {}

    for title, status, planned_start, days in tasks:
        cursor = conn.execute(
            """
            INSERT INTO tasks
            (title, status, planned_start, duration_days)
            VALUES (?, ?, ?, ?)
            """,
            (title, status, planned_start, days),
        )
        ids[title] = cursor.lastrowid

    for waits, prereq in links:
        conn.execute(
            """
            INSERT INTO dependencies
            (task_id, depends_on_id)
            VALUES (?, ?)
            """,
            (ids[waits], ids[prereq]),
        )

    recalculate(conn)
    return ids


def row(conn, title):
    return conn.execute(
        "SELECT * FROM tasks WHERE title = ?",
        (title,),
    ).fetchone()


def set_status(conn, title, status):
    conn.execute(
        "UPDATE tasks SET status = ? WHERE title = ?",
        (status, title),
    )
    recalculate(conn)


DIAMOND = [
    ("Requirements", "Done", "2026-01-01", 3),
    ("Schema", "Done", "2026-01-01", 2),
    ("API design", "Done", "2026-01-01", 2),
    ("Backend", "Review", "2026-01-01", 5),
    ("Deploy", "Backlog", "2026-01-01", 1),
]


DIAMOND_LINKS = [
    ("Schema", "Requirements"),
    ("API design", "Requirements"),
    ("Backend", "Schema"),
    ("Backend", "API design"),
    ("Deploy", "Backend"),
]


def test_start_is_the_latest_end_of_the_direct_prerequisites(conn):
    build(conn, DIAMOND, DIAMOND_LINKS)

    assert row(conn, "Requirements")["end_date"] == "2026-01-04"
    assert row(conn, "Schema")["start_date"] == "2026-01-04"
    assert row(conn, "Backend")["start_date"] == "2026-01-06"
    assert row(conn, "Backend")["end_date"] == "2026-01-11"


def test_a_three_day_slip_moves_the_diamond_by_three_not_six(conn):
    build(conn, DIAMOND, DIAMOND_LINKS)

    conn.execute(
        "UPDATE tasks SET duration_days = 6 WHERE title = 'Requirements'"
    )
    recalculate(conn)

    assert row(conn, "Backend")["start_date"] == "2026-01-09"
    assert row(conn, "Deploy")["start_date"] == "2026-01-14"


def test_planned_start_is_a_not_earlier_than_date(conn):
    build(
        conn,
        [
            ("Prep", "Done", "2026-01-01", 2),
            ("Launch", "Backlog", "2026-03-01", 1),
        ],
        [("Launch", "Prep")],
    )

    assert row(conn, "Launch")["start_date"] == "2026-03-01"


def test_prerequisites_win_when_they_end_after_the_planned_start(conn):
    build(
        conn,
        [
            ("Prep", "Done", "2026-01-01", 10),
            ("Launch", "Backlog", "2026-01-02", 1),
        ],
        [("Launch", "Prep")],
    )

    assert row(conn, "Launch")["start_date"] == "2026-01-11"


def test_nothing_is_blocked_while_every_prerequisite_is_done(conn):
    build(conn, DIAMOND, DIAMOND_LINKS)

    assert row(conn, "Backend")["is_blocked"] == 0
    assert row(conn, "Deploy")["is_blocked"] == 1


def test_reopening_a_task_blocks_everything_downstream(conn):
    build(conn, DIAMOND, DIAMOND_LINKS)

    set_status(conn, "Requirements", "In Progress")

    for title in ("Schema", "API design", "Backend", "Deploy"):
        assert row(conn, title)["is_blocked"] == 1

    assert row(conn, "Requirements")["is_blocked"] == 0


def test_blocking_cascades_through_tasks_that_are_still_done(conn):
    build(conn, DIAMOND, DIAMOND_LINKS)

    set_status(conn, "Requirements", "In Progress")

    assert row(conn, "Schema")["status"] == "Done"
    assert row(conn, "API design")["status"] == "Done"
    assert row(conn, "Backend")["is_blocked"] == 1


def test_rollback_never_moves_a_card_to_another_column(conn):
    build(conn, DIAMOND, DIAMOND_LINKS)

    set_status(conn, "Requirements", "In Progress")

    assert row(conn, "Schema")["status"] == "Done"
    assert row(conn, "Backend")["status"] == "Review"
    assert row(conn, "Deploy")["status"] == "Backlog"


def test_finishing_again_unblocks_and_every_card_is_where_it_was(conn):
    build(conn, DIAMOND, DIAMOND_LINKS)

    set_status(conn, "Requirements", "In Progress")
    set_status(conn, "Requirements", "Done")

    assert row(conn, "Backend")["is_blocked"] == 0
    assert row(conn, "Backend")["status"] == "Review"


def test_critical_path_finds_the_longest_chain(conn):
    build(
        conn,
        [
            ("Requirements", "Done", "2026-01-01", 3),
            ("Schema", "Backlog", "2026-01-01", 2),
            ("API design", "Backlog", "2026-01-01", 4),
            ("Backend", "Backlog", "2026-01-01", 5),
        ],
        [
            ("Schema", "Requirements"),
            ("API design", "Requirements"),
            ("Backend", "Schema"),
            ("Backend", "API design"),
        ],
    )

    tasks, edges = load_graph(conn)
    slack = critical_path(tasks, edges)

    by_title = {
        tasks[task_id]["title"]: days
        for task_id, days in slack.items()
    }

    assert by_title == {
        "Requirements": 0,
        "Schema": 2,
        "API design": 0,
        "Backend": 0,
    }


def test_critical_path_of_an_empty_board_is_empty():
    assert critical_path({}, []) == {}