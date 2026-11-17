"""Extractor interface. Every extractor (rules, Textract + Bedrock, hybrid)
implements this, so the pipeline and the evaluation harness can swap them."""

from __future__ import annotations

from typing import Protocol

from docintel.schemas import DocType, ExtractedField


class Extractor(Protocol):
    name: str

    def classify(self, text: str) -> DocType: ...

    def extract(self, text: str, doc_type: DocType) -> list[ExtractedField]: ...
