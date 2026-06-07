"""
Module for SQLite database management.
Store them in a SQLite database for later retrieval and analysis.
"""

import json
import sqlite3
import pandas as pd

JSONL_PATH = "D:/My Documents/Dev_Python/Personal Multi-LLM Review Automation Tool/resources/logs/OpenAI/gpt_response_log_20260605_153559.jsonl"
OPENAI_DB_PATH = "D:/My Documents/Dev_Python/Personal Multi-LLM Review Automation Tool/resources/db/sqlite.db"

cmd = """CREATE TABLE IF NOT EXISTS my_table (
        id INTEGER PRIMARY KEY,
        data_json TEXT)"""


def load_json(jsonl_path) -> dict:
    """
    Load the jsonl file about LLM's log and convert it into a dict.
    """
    with open(jsonl_path, "r", encoding="utf-8") as file:
        record = json.load(file)
        return record


def insert_log_record(conn: sqlite3.Connection, record: dict) -> None:
    return None


def import_jsonl_to_sqlite(jsonl_path: str, db_path: str) -> None:
    conn = sqlite3.connect(db_path)

    record = load_json(jsonl_path)

    df = pd.json_normalize(record)

    df.to_sql("gpt_logs", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    print(f"리스트 출력: {load_json(JSONL_PATH)}")
    import_jsonl_to_sqlite(JSONL_PATH, OPENAI_DB_PATH)
    print("데이터베이스 생성 완료")
