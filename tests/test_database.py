import sqlite3

import pytest

from attendance_analyst.database import (
    READ_QUERY,
    QueryRejected,
    create_readonly_connection,
    execute_readonly_query,
    load_synthetic_rows,
)


def test_approved_query_is_parameterized_and_returns_rows():
    rows = load_synthetic_rows()
    connection = create_readonly_connection(rows)
    try:
        result = execute_readonly_query(connection, READ_QUERY, ("2026-01-05", "2026-01-05", 20))
        assert len(result) == 5
        assert all(row["work_date"] == "2026-01-05" for row in result)
    finally:
        connection.close()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE attendance_records SET department='x'",
        "DELETE FROM attendance_records",
        "SELECT * FROM sqlite_master",
        READ_QUERY + "; DELETE FROM attendance_records",
    ],
)
def test_non_allowlisted_or_mutating_sql_is_rejected(sql):
    connection = create_readonly_connection(load_synthetic_rows())
    try:
        with pytest.raises(QueryRejected):
            execute_readonly_query(connection, sql, ("2026-01-05", "2026-01-09", 100))
    finally:
        connection.close()


def test_sqlite_connection_itself_is_locked_against_writes():
    connection = create_readonly_connection(load_synthetic_rows())
    try:
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("UPDATE attendance_records SET department='changed'")
    finally:
        connection.close()


def test_date_input_is_bound_as_a_value_and_invalid_injection_is_rejected():
    connection = create_readonly_connection(load_synthetic_rows())
    try:
        with pytest.raises(QueryRejected):
            execute_readonly_query(connection, READ_QUERY, ("2026-01-05' OR 1=1 --", "2026-01-09", 100))
    finally:
        connection.close()


def test_query_limit_allows_only_one_lookahead_row_above_retry_cap():
    connection = create_readonly_connection(load_synthetic_rows())
    try:
        with pytest.raises(QueryRejected):
            execute_readonly_query(connection, READ_QUERY, ("2026-01-05", "2026-01-09", 5_002))
    finally:
        connection.close()
