# tests/conftest.py

import pytest
import database


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    temp_file = tmp_path / "test.db"

    monkeypatch.setattr(
        database,
        "DB_PATH",
        temp_file
    )

    database.init_db()

    return temp_file


@pytest.fixture
def conn(db_path):
    connection = database.get_connection()

    yield connection

    connection.close()