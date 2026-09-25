# database.py

import sqlite3
from contextlib import contextmanager
from pathlib import Path


DB_PATH = Path(__file__).parent / "taskflow.db"


COLUMNS = ["Backlog", "In Progress", "Review", "Done"]


# Database schema.
SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Backlog',
    planned_start TEXT NOT NULL,
    duration_days INTEGER NOT NULL DEFAULT 1,
    start_date TEXT,
    end_date TEXT,
    is_blocked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    depends_on_id INTEGER NOT NULL,

    UNIQUE (task_id, depends_on_id),

    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_id) REFERENCES tasks(id) ON DELETE CASCADE
);
"""


def get_connection():
    """Open a fresh connection to the database file."""
    conn = sqlite3.connect(DB_PATH)

    
    conn.row_factory = sqlite3.Row


    conn.execute("PRAGMA foreign_keys = ON")

    return conn


@contextmanager
def db():
    """
    Open a database connection, commit successful changes,
    and always close the connection.
    """
    conn = get_connection()

    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create the tables if they do not exist yet."""
    with db() as conn:
        conn.executescript(SCHEMA)

    print("Database ready at " + str(DB_PATH))


if __name__ == "__main__":
    init_db()