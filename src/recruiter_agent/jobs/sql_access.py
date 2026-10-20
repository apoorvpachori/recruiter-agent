"""Read-only SQL access scoped to the jobs table for agent questions."""

import re
import sqlite3
from enum import Enum
from pathlib import Path
from typing import Any

from recruiter_agent.settings import get_settings

MAX_SQL_ROWS = 100
MAX_SQL_LENGTH = 2_000
_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|replace|drop|alter|create|attach|detach|pragma|vacuum|reindex|"
    r"begin|commit|rollback|savepoint|release|grant|revoke|load_extension)\b",
    re.IGNORECASE,
)
_TABLE_REFERENCE = re.compile(
    r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)(?:\s*\.\s*([a-z_][a-z0-9_]*))?",
    re.IGNORECASE,
)
_SELECT_LIMIT = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)

JOBS_TABLE_SCHEMA: tuple[dict[str, str], ...] = (
    {"name": "id", "type": "integer", "description": "Primary key."},
    {"name": "url", "type": "text", "description": "Unique public job posting URL."},
    {"name": "company", "type": "text", "description": "Company name, if known."},
    {"name": "title", "type": "text", "description": "Job title, if known."},
    {"name": "status", "type": "text", "description": "Current application status."},
    {"name": "notes", "type": "text", "description": "User notes; may be null."},
    {"name": "created_at", "type": "text", "description": "UTC creation timestamp."},
    {"name": "updated_at", "type": "text", "description": "UTC last-update timestamp."},
)


def _database_path() -> Path:
    database_url = get_settings().database_url
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Agent SQL access currently supports only local SQLite databases.")
    return Path(database_url[len(prefix) :]).expanduser().resolve()


def get_jobs_schema() -> dict[str, Any]:
    """Return the only table/schema the agent SQL tool may access."""
    return {"table": "jobs", "columns": list(JOBS_TABLE_SCHEMA), "access": "read_only"}


def run_jobs_sql(query: str) -> dict[str, Any]:
    """Run one read-only SELECT against jobs; writes and other tables are refused."""
    statement = query.strip()
    if not statement or len(statement) > MAX_SQL_LENGTH:
        raise ValueError(f"SQL must be between 1 and {MAX_SQL_LENGTH} characters.")
    if ";" in statement or "--" in statement or "/*" in statement or "*/" in statement:
        raise ValueError("Only one simple read-only SQL statement is allowed.")
    if not re.match(r"(?is)^select\b", statement):
        raise ValueError("Only SELECT statements are allowed.")
    if _FORBIDDEN_SQL.search(statement):
        raise ValueError("The query contains a forbidden SQL operation.")

    tables = _TABLE_REFERENCE.findall(statement)
    if not tables or any(
        (schema and schema.casefold() != "main") or table.casefold() != "jobs"
        for table, schema in tables
    ):
        raise ValueError("Queries may reference only the jobs table.")

    if not _SELECT_LIMIT.search(statement):
        statement = f"{statement.rstrip(';')} LIMIT {MAX_SQL_ROWS}"

    path = _database_path()
    if not path.exists():
        return {"columns": [], "rows": [], "row_count": 0}

    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2.0)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.execute(statement)
        rows = [
            {
                key: value.value if isinstance(value, Enum) else value
                for key, value in dict(row).items()
            }
            for row in cursor.fetchmany(MAX_SQL_ROWS)
        ]
        return {
            "columns": [column[0] for column in cursor.description or []],
            "rows": rows,
            "row_count": len(rows),
        }
    except sqlite3.Error as exc:
        raise ValueError(f"Query could not be run against the jobs table: {exc}") from exc
    finally:
        connection.close()
