"""
share_knowledge: Cross-agent knowledge tool for Olympus.

Reads/writes shared facts from the Olympus SQLite database.
Scope access is enforced in application logic: each agent's tool config
specifies which scopes it can read and write.
"""
import sqlite3
import uuid
from typing import Literal
from pathlib import Path


class ShareKnowledgeTool:
    """Hermes tool plugin for cross-agent knowledge sharing."""

    name = "share_knowledge"
    description = "Write, query, or delete cross-agent knowledge facts."

    def __init__(self, db_path: str | Path, allowed_scopes: list[str] | None = None):
        """
        Args:
            db_path: Path to the shared SQLite database.
            allowed_scopes: List of scopes this agent can access.
                           None means all scopes (for Zeus).
        """
        self.db_path = Path(db_path)
        self.allowed_scopes = allowed_scopes  # None = all scopes

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _check_scope(self, scope: str):
        if self.allowed_scopes is not None and scope not in self.allowed_scopes:
            raise PermissionError(
                f"Agent not authorized for scope '{scope}'. Allowed: {self.allowed_scopes}"
            )

    def __call__(
        self,
        action: Literal["write", "query", "delete"],
        scope: Literal["personal", "business", "global"],
        domain: str,
        fact: str | None = None,
        confidence: float = 1.0,
        limit: int = 10,
    ) -> dict:
        """Execute a share_knowledge action."""
        try:
            self._check_scope(scope)
        except PermissionError as e:
            return {"error": str(e)}

        if action == "write":
            return self._write(scope, domain, fact, confidence)
        elif action == "query":
            return self._query(scope, domain, limit)
        elif action == "delete":
            return self._delete(scope, domain, fact)
        else:
            return {"error": f"Unknown action: {action}"}

    def _write(self, scope: str, domain: str, fact: str, confidence: float) -> dict:
        if not fact:
            return {"error": "fact is required for write action"}

        conn = self._connect()
        try:
            fact_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO olympus_knowledge (id, scope, domain, fact, confidence, source_profile)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (fact_id, scope, domain, fact, confidence, "current_agent"),
            )
            conn.commit()
            return {"status": "written", "id": fact_id}
        except sqlite3.Error as e:
            return {"error": str(e)}
        finally:
            conn.close()

    def _query(self, scope: str, domain: str, limit: int) -> dict:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT id, domain, fact, confidence, source_profile, created_at
                FROM olympus_knowledge
                WHERE scope = ? AND domain = ?
                ORDER BY rowid DESC
                LIMIT ?
                """,
                (scope, domain, limit),
            ).fetchall()

            return {
                "status": "ok",
                "facts": [
                    {
                        "id": row["id"],
                        "domain": row["domain"],
                        "fact": row["fact"],
                        "confidence": row["confidence"],
                        "source_profile": row["source_profile"],
                        "created_at": row["created_at"],
                    }
                    for row in rows
                ],
                "count": len(rows),
            }
        except sqlite3.Error as e:
            return {"error": str(e)}
        finally:
            conn.close()

    def _delete(self, scope: str, domain: str, fact: str | None) -> dict:
        if not fact:
            return {"error": "fact is required for delete action"}

        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM olympus_knowledge WHERE scope = ? AND domain = ? AND fact = ?",
                (scope, domain, fact),
            )
            conn.commit()
            return {"status": "deleted", "rows_affected": cursor.rowcount}
        except sqlite3.Error as e:
            return {"error": str(e)}
        finally:
            conn.close()
