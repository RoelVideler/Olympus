"""Document ingestion skill — parse documents and extract structured facts.

Supports CSV, JSON, text, and markdown files. Extracts domain-relevant facts
and stores them via share_knowledge for cross-agent access.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

INGEST_SCHEMA = {
    "name": "document_ingest",
    "description": "Ingest a document and extract structured facts for knowledge storage.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["ingest", "status", "list"],
                "description": "Action: ingest a document, check ingestion status, or list ingested documents.",
            },
            "file_path": {
                "type": "string",
                "description": "Path to the document file to ingest.",
            },
            "document_type": {
                "type": "string",
                "enum": ["csv", "json", "text", "markdown", "auto"],
                "description": "Document type. 'auto' detects from file extension.",
                "default": "auto",
            },
            "domain": {
                "type": "string",
                "description": "Domain category for extracted facts (e.g., 'health', 'finance', 'relationships').",
            },
            "scope": {
                "type": "string",
                "enum": ["personal", "business", "global"],
                "description": "Knowledge scope for extracted facts.",
                "default": "personal",
            },
        },
        "required": ["action"],
    },
}

INGEST_STATE_DIR = Path.home() / ".hermes" / "olympus" / "ingestion"
DOCUMENT_TYPES = {
    ".csv": "csv",
    ".json": "json",
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
}


def _load_state() -> dict:
    """Load ingestion state."""
    state_file = INGEST_STATE_DIR / "state.json"
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {"documents": [], "total_facts": 0}


def _save_state(state: dict) -> None:
    """Save ingestion state."""
    INGEST_STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(INGEST_STATE_DIR / "state.json", "w") as f:
        json.dump(state, f, indent=2)


def _detect_type(file_path: str) -> str:
    """Detect document type from file extension."""
    ext = Path(file_path).suffix.lower()
    return DOCUMENT_TYPES.get(ext, "text")


def _parse_csv(content: str) -> list[dict]:
    """Parse CSV content into structured records."""
    reader = csv.DictReader(io.StringIO(content))
    return [row for row in reader]


def _parse_json(content: str) -> list[dict] | dict:
    """Parse JSON content."""
    data = json.loads(content)
    if isinstance(data, list):
        return data
    return [data]


def _parse_text(content: str) -> list[str]:
    """Parse text content into paragraphs."""
    return [p.strip() for p in content.split("\n\n") if p.strip()]


def _parse_markdown(content: str) -> list[str]:
    """Parse markdown content into sections."""
    sections = []
    current_section = []
    current_heading = None

    for line in content.split("\n"):
        if line.startswith("#"):
            if current_section:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_section).strip(),
                })
            current_heading = line.lstrip("# ").strip()
            current_section = []
        else:
            current_section.append(line)

    if current_section:
        sections.append({
            "heading": current_heading,
            "content": "\n".join(current_section).strip(),
        })

    return sections


def handle_document_ingest(args: dict, **kw) -> dict[str, Any]:
    """Handle a document ingestion request.

    Args:
        args: Dict with 'action', optional 'file_path', 'document_type', 'domain', 'scope'.

    Returns:
        Dict with ingestion results or status.
    """
    action = args.get("action", "status")
    state = _load_state()

    if action == "list":
        return {
            "status": "ok",
            "documents": state.get("documents", []),
            "total_facts": state.get("total_facts", 0),
        }

    if action == "status":
        doc_count = len(state.get("documents", []))
        doc_types = set(d.get("type", "unknown") for d in state.get("documents", []))
        return {
            "status": "ok",
            "documents_ingested": doc_count,
            "document_types": list(doc_types),
            "total_facts_extracted": state.get("total_facts", 0),
        }

    if action == "ingest":
        file_path = args.get("file_path")
        if not file_path:
            return {"error": "file_path is required for ingest action"}

        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        doc_type = args.get("document_type", "auto")
        if doc_type == "auto":
            doc_type = _detect_type(file_path)

        domain = args.get("domain", "general")
        scope = args.get("scope", "personal")

        try:
            content = path.read_text()
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

        if doc_type == "csv":
            records = _parse_csv(content)
            facts = [f"Record: {', '.join(f'{k}={v}' for k, v in row.items())}" for row in records]
        elif doc_type == "json":
            records = _parse_json(content)
            facts = [f"Data: {json.dumps(record)}" for record in records]
        elif doc_type == "markdown":
            sections = _parse_markdown(content)
            facts = [f"Section '{s['heading']}': {s['content']}" for s in sections if s.get("content")]
        else:
            facts = _parse_text(content)

        facts = [f for f in facts if f]

        # Update state
        doc_entry = {
            "file_path": str(path),
            "type": doc_type,
            "domain": domain,
            "scope": scope,
            "facts_extracted": len(facts),
        }
        state.setdefault("documents", []).append(doc_entry)
        state["total_facts"] = state.get("total_facts", 0) + len(facts)
        _save_state(state)

        return {
            "status": "ok",
            "document_type": doc_type,
            "domain": domain,
            "scope": scope,
            "facts_extracted": len(facts),
            "facts": facts[:10],  # Return first 10 for preview
            "total_facts": len(facts),
            "guidance": (
                f"Extracted {len(facts)} facts from {path.name}. "
                f"Use share_knowledge to store them with scope='{scope}' and domain='{domain}'. "
                f"Each fact should be written individually for proper tracking."
            ),
        }

    return {"error": f"Unknown action: {action}"}
