# tests/test_graph.py

from graph import creates_cycle, topological_sort


TASK_IDS = [1, 2, 3, 4, 5]

EDGES = [
    (2, 1),
    (3, 1),
    (4, 2),
    (4, 3),
    (5, 4),
]


def test_order_puts_every_prerequisite_first():
    order = topological_sort(TASK_IDS, EDGES)

    assert order == [1, 2, 3, 4, 5]


def test_closing_a_loop_is_detected():
    assert creates_cycle(
        TASK_IDS,
        EDGES,
        (1, 5)
    ) is True


def test_problem_statement_example_a_b_c_a():
    assert creates_cycle(
        [1, 2, 3],
        [
            (2, 1),
            (3, 2)
        ],
        (1, 3)
    ) is True


def test_legal_dependency_is_allowed():
    assert creates_cycle(
        TASK_IDS,
        EDGES,
        (3, 2)
    ) is False


def test_task_cannot_wait_for_itself():
    assert creates_cycle(
        TASK_IDS,
        EDGES,
        (2, 2)
    ) is True


def test_cycle_check_leaves_graph_untouched():
    edges = list(EDGES)

    creates_cycle(
        TASK_IDS,
        edges,
        (1, 5)
    )

    assert edges == EDGES


def test_sorting_graph_that_already_loops_returns_none():
    assert topological_sort(
        [1, 2],
        [
            (1, 2),
            (2, 1)
        ]
    ) is None