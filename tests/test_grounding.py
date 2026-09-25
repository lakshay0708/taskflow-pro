import ai_suggest
import database
import main
import seed


def seeded_board():
    seed.main()

    with database.db() as conn:
        tasks = {
            row["id"]: dict(row)
            for row in conn.execute(
                "SELECT * FROM tasks"
            )
        }

        task_ids, edges = main.load_ids_and_edges(conn)

    return tasks, task_ids, edges


def title_to_id(tasks, title):
    return [
        task_id
        for task_id, task in tasks.items()
        if task["title"] == title
    ][0]


def test_invented_and_malformed_suggestions_are_all_dropped(
    db_path,
):
    tasks, task_ids, edges = seeded_board()

    target = title_to_id(
        tasks,
        "Deploy to production",
    )

    lies = [
        {
            "id": 99999,
            "reason": "a task that does not exist",
        },
        {
            "id": "notanumber",
            "reason": "not even a number",
        },
        {
            "id": target,
            "reason": "the new task itself",
        },
        {
            "id": None,
            "reason": "nothing at all",
        },
        "this is not even an object",
    ]

    assert main.ground_suggestions(
        lies,
        tasks,
        task_ids,
        edges,
        target,
    ) == []


def test_a_real_suggestion_survives_with_our_own_title(
    db_path,
):
    tasks, task_ids, edges = seeded_board()

    target = title_to_id(
        tasks,
        "Deploy to production",
    )

    kickoff = title_to_id(
        tasks,
        "Project kickoff",
    )

    kept = main.ground_suggestions(
        [
            {
                "id": kickoff,
                "title": "A TITLE THE MODEL MADE UP",
                "reason": "real",
            }
        ],
        tasks,
        task_ids,
        edges,
        target,
    )

    assert kept == [
        {
            "id": kickoff,
            "title": "Project kickoff",
            "reason": "real",
        }
    ]


def test_a_suggestion_that_would_close_a_loop_is_dropped(
    db_path,
):
    tasks, task_ids, edges = seeded_board()

    upstream = title_to_id(
        tasks,
        "Gather requirements",
    )

    downstream = title_to_id(
        tasks,
        "Deploy to production",
    )

    kept = main.ground_suggestions(
        [
            {
                "id": downstream,
                "reason": "would loop",
            }
        ],
        tasks,
        task_ids,
        edges,
        upstream,
    )

    assert kept == []


def test_the_keyword_fallback_needs_no_network(
    db_path,
    monkeypatch,
):
    monkeypatch.setattr(
        ai_suggest,
        "call_llm",
        lambda prompt: None,
    )

    seed.main()

    new_id = main.create_task(
        main.TaskIn(
            title="Integration testing for payments"
        )
    )["created_id"]

    result = main.suggest_prerequisites(
        main.SuggestIn(task_id=new_id)
    )

    with database.db() as conn:
        real_ids = {
            row["id"]
            for row in conn.execute(
                "SELECT id FROM tasks"
            )
        }

    assert result["source"] == "keyword"
    assert result["requires_approval"] is True
    assert result["suggestions"]

    for suggestion in result["suggestions"]:
        assert suggestion["id"] in real_ids
        assert suggestion["id"] != new_id