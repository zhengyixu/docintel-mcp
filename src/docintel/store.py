"""File-backed result store. One JSON file per document id.

Swap for DynamoDB later; the interface (save/get) stays the same.
"""

from __future__ import annotations

import re
from pathlib import Path

from docintel.schemas import ExtractionResult

DOCUMENT_ID = re.compile(r"^doc_[0-9a-f]{12}$")


class ResultStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, document_id: str) -> Path:
        # Ids come from an AI agent: validate before touching the filesystem.
        if not DOCUMENT_ID.match(document_id):
            raise ValueError(f"Invalid document id: {document_id!r}")
        return self.directory / f"{document_id}.json"

    def save(self, result: ExtractionResult) -> None:
        self._path(result.document_id).write_text(result.model_dump_json(indent=2), encoding="utf-8")

    def get(self, document_id: str) -> ExtractionResult | None:
        path = self._path(document_id)
        if not path.exists():
            return None
        return ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
