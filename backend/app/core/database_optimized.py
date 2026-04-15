"""
Compatibility shim for older imports.

Canonical implementation lives in `app.core.database`.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import text

from .database import *  # noqa: F403
from .database import engine, execute_query_with_retry, get_table_schema
from .cache_manager import cached


def get_table_stats(table_name: str) -> Dict[str, Any]:
    """Best-effort table stats for tests (row count only)."""
    if engine is None:
        return {"table_name": table_name, "status": "unavailable"}
    try:
        schema = get_table_schema(table_name)
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row = result.fetchone()
        return {"table_name": table_name, "row_count": int(row[0]) if row else 0, "schema": schema}
    except Exception as e:
        return {"table_name": table_name, "error": str(e)}


@cached(ttl=5, key_prefix="dbq:")
def execute_query_cached(query: str, params: Optional[dict] = None):
    return execute_query_with_retry(query, params=params)


def execute_batch_queries(queries: Sequence[Tuple[str, Optional[dict]]]) -> List[Any]:
    """Execute a list of queries sequentially (test helper)."""
    results: List[Any] = []
    for q, p in queries:
        results.append(execute_query_with_retry(q, params=p))
    return results


def get_database_metrics() -> Dict[str, Any]:
    """Compatibility wrapper; returns database stats if available."""
    try:
        return get_database_stats()
    except Exception as e:
        return {"error": str(e)}


def optimize_database() -> Dict[str, Any]:
    """No-op optimization hook for tests."""
    return {"status": "ok", "message": "No optimizer configured"}


