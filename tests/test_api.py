import pytest
from fastapi import HTTPException

import database
import main
from main import DependencyIn, DurationIn, StatusIn, TaskIn


def new_task(title, days=1):
    result = main.create_task(
        TaskIn(
            title=title,
            duration_days=days,
            planned_start="2026-01-01",
        )
    )
    return result["created_id"]


def link(waits, prereq):
    return main.add_dependency(
        DependencyIn(
            task_id=waits,
            depends_on_id=prereq,
        )
    )


def move(task_id, status):
    return main.move_task(
        task_id,
        StatusIn(status=status),
    )


def task_in(board, task_id):
    return [
        task
        for task in board["tasks"]
        if task["id"] == task_id
    ][0]


def test_a_cycle_is_rejected_with_409_and_the_graph_is_unchanged(db_path):
    a, b, c = (
        new_task("A"),
        new_task("B"),
        new_task("C"),
    )

    link(b, a)
    link(c, b)

    before = main.get_board()["dependencies"]

    with pytest.raises(HTTPException) as error:
        link(a, c)

    assert error.value.status_code == 409
    assert "circular" in error.value.detail
    assert main.get_board()["dependencies"] == before


def test_a_task_cannot_depend_on_itself(db_path):
    a = new_task("A")

    with pytest.raises(HTTPException) as error:
        link(a, a)

    assert error.value.status_code == 409


def test_a_longer_upstream_task_moves_the_diamond_once(db_path):
    a, b, c, d = (
        new_task("A", 3),
        new_task("B", 2),
        new_task("C", 2),
        new_task("D", 1),
    )

    link(b, a)
    link(c, a)
    link(d, b)
    link(d, c)

    assert (
        task_in(main.get_board(), d)["start_date"]
        == "2026-01-06"
    )

    board = main.change_duration(
        a,
        DurationIn(duration_days=6),
    )["board"]

    assert (
        task_in(board, d)["start_date"]
        == "2026-01-09"
    )


def test_a_duration_below_one_day_is_refused(db_path):
    a = new_task("A")

    with pytest.raises(HTTPException) as error:
        main.change_duration(
            a,
            DurationIn(duration_days=0),
        )

    assert error.value.status_code == 400


def test_a_blocked_task_cannot_move_forward(db_path):
    a, b = new_task("A"), new_task("B")

    link(b, a)

    with pytest.raises(HTTPException) as error:
        move(b, "In Progress")

    assert error.value.status_code == 409


def test_rollback_flags_the_card_but_leaves_it_in_its_column(db_path):
    a, b = new_task("A"), new_task("B")

    link(b, a)

    move(a, "Done")
    move(b, "Review")

    board = move(a, "In Progress")["board"]

    assert task_in(board, b)["is_blocked"] == 1
    assert task_in(board, b)["status"] == "Review"


def test_a_blocked_task_may_still_move_backward(db_path):
    a, b = new_task("A"), new_task("B")

    link(b, a)

    move(a, "Done")
    move(b, "Review")
    move(a, "In Progress")

    board = move(b, "In Progress")["board"]

    assert task_in(board, b)["status"] == "In Progress"


def test_everything_is_in_the_database_not_in_memory(db_path):
    a, b = new_task("A"), new_task("B")

    link(b, a)
    move(a, "Done")

    with database.db() as conn:
        status = conn.execute(
            "SELECT status FROM tasks WHERE id = ?",
            (a,),
        ).fetchone()[0]

        links = conn.execute(
            "SELECT COUNT(*) FROM dependencies"
        ).fetchone()[0]

    assert status == "Done"
    assert links == 1


def test_the_board_reports_slack_and_the_critical_path(db_path):
    a, b, c = (
        new_task("A", days=2),
        new_task("B", days=1),
        new_task("C", days=1),
    )

    board = link(b, a)["board"]

    assert task_in(board, a)["is_critical"] == 1
    assert task_in(board, b)["is_critical"] == 1
    assert task_in(board, c)["is_critical"] == 0
    assert task_in(board, c)["slack_days"] == 2