import seed
from database import db
from engine import recalculate


seed.main()

before = {}

with db() as conn:
    for row in conn.execute(
        "SELECT title, start_date FROM tasks ORDER BY id"
    ):
        before[row["title"]] = seed.day_number(
            row["start_date"]
        )

with db() as conn:
    conn.execute(
        """
        UPDATE tasks
        SET duration_days = 6
        WHERE title = 'Gather requirements'
        """
    )
    recalculate(conn)

print(
    "\n'Gather requirements' grew from 3 days to 6 days: "
    "a 3-day slip.\n"
)

print("task was now moved")
print("-------------------------- ------- ------- -----")

with db() as conn:
    for row in conn.execute(
        "SELECT title, start_date FROM tasks ORDER BY id"
    ):
        now = seed.day_number(row["start_date"])
        was = before[row["title"]]

        print(
            "%-26s day %-3d day %-3d %+d"
            % (
                row["title"],
                was,
                now,
                now - was,
            )
        )

print("\nEvery downstream task must show +3, never +6.")
print("Run 'python seed.py' to put the board back.")