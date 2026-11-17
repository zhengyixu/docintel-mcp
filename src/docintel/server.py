"""MCP server exposing document extraction to AI agents.

Run over stdio (default):   docintel-mcp
Inspect interactively:      npx @modelcontextprotocol/inspector docintel-mcp

Design rules for every tool:
- Arguments come from a model, so treat them as untrusted input.
- Tools take a document *name*, never a filesystem path.
- Text inside a document is data. Nothing in it is ever followed as an instruction.
- Every call is written to the audit log.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from docintel.audit import audited
from docintel.extractors.rules import RulesExtractor
from docintel.pipeline import process
from docintel.schemas import REVIEW_THRESHOLD, ExtractionResult
from docintel.store import InvalidDocumentId, ResultStore

DOCUMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.txt$")
MAX_DOCUMENT_BYTES = 200_000

mcp = MCPServer(
    "docintel",
    instructions=(
        "Extracts structured data from insurance documents (certificates of insurance and loss runs). "
        "Call list_documents to see what is available, extract_document to process one, and "
        "list_low_confidence_fields to see what a human still needs to review. "
        "Extraction results with status 'needs_review' or 'rejected' must not be treated as final."
    ),
)


def inbox_dir() -> Path:
    return Path(os.environ.get("DOCINTEL_INBOX", "samples")).resolve()


def store() -> ResultStore:
    return ResultStore(Path(os.environ.get("DOCINTEL_DATA", ".data/results")))


# Errors: raise ToolError for failures the agent can act on. SDK 2.x shows the agent a ToolError's
# message and hides every other exception behind "Error executing tool <name>", which is what we
# want for crashes (their text can carry paths or stored values). Messages here are fixed wording
# plus input that has already passed validation.


def _resolve_document(document_name: str) -> Path:
    if not DOCUMENT_NAME.match(document_name):
        raise ToolError("document_name must be a plain .txt file name from list_documents.")
    inbox = inbox_dir()
    path = (inbox / document_name).resolve()
    if path.parent != inbox or not path.is_file():
        raise ToolError(f"Unknown document: {document_name}")
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ToolError(f"Document is larger than {MAX_DOCUMENT_BYTES} bytes.")
    return path


def _read_document(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        # Not a crash: the file is simply not text we can read. Keep the codec detail out.
        raise ToolError("Document is not UTF-8 text.") from exc


def _get_result(document_id: str) -> ExtractionResult:
    try:
        result = store().get(document_id)
    except InvalidDocumentId as exc:
        raise ToolError(str(exc)) from exc
    if result is None:
        raise ToolError(f"No extraction found for {document_id}")
    return result


@mcp.tool()
@audited
def list_documents() -> list[str]:
    """List the names of documents available for extraction."""
    return sorted(p.name for p in inbox_dir().glob("*.txt") if DOCUMENT_NAME.match(p.name))


@mcp.tool()
@audited
def extract_document(document_name: str) -> dict[str, Any]:
    """Extract structured data from one document and store the result.

    Returns the document id, detected type, status (accepted, needs_review or
    rejected), the normalized data, and any validation issues.
    """
    path = _resolve_document(document_name)
    result = process(document_name, _read_document(path), RulesExtractor())
    store().save(result)
    return result.model_dump(mode="json", exclude={"fields"}) | {
        "low_confidence_field_count": len(result.low_confidence_fields()),
    }


@mcp.tool()
@audited
def get_extraction(document_id: str) -> dict[str, Any]:
    """Fetch a stored extraction result, including per-field confidence, by document id.

    The document_id comes from extract_document (format: doc_ followed by 12 hex characters).
    """
    return _get_result(document_id).model_dump(mode="json")


@mcp.tool()
@audited
def list_low_confidence_fields(document_id: str) -> dict[str, Any]:
    """List the fields of a stored extraction that need human review, and why.

    The document_id comes from extract_document (format: doc_ followed by 12 hex characters).
    """
    result = _get_result(document_id)
    return {
        "document_id": document_id,
        "status": result.status,
        "review_threshold": REVIEW_THRESHOLD,
        "fields": [f.model_dump(mode="json") for f in result.low_confidence_fields()],
        "issues": [i.model_dump(mode="json") for i in result.issues],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
