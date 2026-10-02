"""Synthetic fixture loader and a tightly constrained read-only SQL tool."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import sqlite3
from typing import Iterable, Mapping, Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = PROJECT_ROOT / "data" / "synthetic_attendance.csv"
ALLOWED_TABLE = "attendance_records"
INITIAL_ROW_LIMIT = 500
RETRY_ROW_LIMIT = 5_000

READ_QUERY = """SELECT employee_key, work_date, department, shift,
       scheduled_start, scheduled_end, actual_check_in, actual_check_out,
       attendance_status, exception_type, source_row_id
FROM attendance_records
WHERE work_date >= ? AND work_date <= ?
ORDER BY work_date, source_row_id
LIMIT ?"""

_NORMALIZED_ALLOWED_QUERY = " ".join(READ_QUERY.casefold().split())
_FIELDS = (
    "employee_key", "work_date", "department", "shift", "scheduled_start",
    "scheduled_end", "actual_check_in", "actual_check_out",
    "attendance_status", "exception_type", "source_row_id",
)


class QueryRejected(ValueError):
    """Raised when a query is outside the single approved read-only shape."""


def load_synthetic_rows(csv_path: Path = DEFAULT_CSV) -> list[dict[str, str | None]]:
    import csv

    if not csv_path.exists():
        raise FileNotFoundError(f"Synthetic attendance fixture not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != _FIELDS:
            raise ValueError(f"Fixture columns must be exactly: {', '.join(_FIELDS)}")
        return [
            {key: (value.strip() or None) if value is not None else None for key, value in row.items()}
            for row in reader
        ]


def _authorize_read_only(action: int, arg1: str | None, arg2: str | None, db_name: str | None, trigger: str | None) -> int:
    del arg2, trigger
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and arg1 == ALLOWED_TABLE and db_name == "main":
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def create_readonly_connection(rows: Iterable[Mapping[str, Any]]) -> sqlite3.Connection:
    """Create a transient synthetic database, then lock its query connection."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    columns = ", ".join(f"{field} TEXT" for field in _FIELDS)
    connection.execute(f"CREATE TABLE {ALLOWED_TABLE} ({columns})")
    placeholders = ", ".join("?" for _ in _FIELDS)
    insert_sql = f"INSERT INTO {ALLOWED_TABLE} ({', '.join(_FIELDS)}) VALUES ({placeholders})"
    values = [tuple(row.get(field) for field in _FIELDS) for row in rows]
    connection.executemany(insert_sql, values)
    connection.execute("PRAGMA query_only = ON")
    connection.set_authorizer(_authorize_read_only)
    return connection


def validate_read_query(sql: str, parameters: tuple[object, ...]) -> None:
    """Accept only the fixed SELECT template and validated bound values."""
    normalized = " ".join(sql.casefold().split())
    if normalized != _NORMALIZED_ALLOWED_QUERY:
        raise QueryRejected("Only the approved parameterized SELECT from attendance_records is allowed.")
    if len(parameters) != 3:
        raise QueryRejected("The approved query requires start date, end date, and row limit parameters.")
    start_raw, end_raw, limit = parameters
    try:
        start = date.fromisoformat(str(start_raw))
        end = date.fromisoformat(str(end_raw))
    except ValueError as error:
        raise QueryRejected("Query date parameters must be ISO calendar dates.") from error
    if start > end:
        raise QueryRejected("Query start date must not be after end date.")
    if not isinstance(limit, int) or not 1 <= limit <= RETRY_ROW_LIMIT + 1:
        raise QueryRejected(f"Query row limit must be between 1 and {RETRY_ROW_LIMIT + 1}.")


def execute_readonly_query(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[object, ...],
) -> list[dict[str, Any]]:
    validate_read_query(sql, parameters)
    try:
        rows = connection.execute(sql, parameters).fetchall()
    except sqlite3.DatabaseError as error:
        raise QueryRejected(f"SQLite rejected the read-only query: {error}") from error
    return [dict(row) for row in rows]


def read_attendance_rows(
    rows: Iterable[Mapping[str, Any]],
    start_date: str,
    end_date: str,
    limit: int,
) -> list[dict[str, Any]]:
    connection = create_readonly_connection(rows)
    try:
        return execute_readonly_query(connection, READ_QUERY, (start_date, end_date, limit))
    finally:
        connection.close()
