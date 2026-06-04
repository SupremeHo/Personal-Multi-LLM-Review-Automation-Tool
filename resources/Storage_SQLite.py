"""
Module for SQLite database management.
Store them in a SQLite database for later retrieval and analysis.
"""

import sqlite3
import uuid

PATH_TO_OPENAI_DB = "D:/My Documents/Dev_Python/Personal Multi-LLM Review Automation Tool/resources/db/gpt_log.db"


def generate_uuid():
    unique_id = uuid.uuid4()
    while check_id_duplicate(unique_id):
        unique_id = uuid.uuid4()
    return unique_id


def check_id_duplicate(unique_id):
    """
    Logic that checks the duplicated UUID.
    """
    return False


def connect_openai_db():
    generate_uuid()

    try:
        with sqlite3.connect(PATH_TO_OPENAI_DB, isolation_level=None) as conn_openai:
            cursor_openai = conn_openai.cursor()

    except sqlite3.OperationalError as e:
        print(f"sqlite3.OperationalError: {e}")

    cursor_openai.execute(
        """CREATE TABLE IF NOT EXISTS gpt_logs (id INTEGER PRIMARY KEY, run_id TEXT, created_at TEXT, system_prompt TEXT, user_prompt TEXT, )"""
    )


if __name__ == "__main__":
    # connect_openai_db()
    print(generate_uuid())
