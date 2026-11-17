"""extract -> fit to schema -> business rules -> decide status."""

from __future__ import annotations

import hashlib

from pydantic import ValidationError

from docintel.extractors.base import Extractor
from docintel.schemas import (
    DOCUMENT_MODELS,
    CertificateOfInsurance,
    ExtractionResult,
    LossRun,
    ValidationIssue,
)
from docintel.validation import validate_coi, validate_loss_run


def document_id_for(text: str) -> str:
    """Content hash: the same document always gets the same id (idempotent re-runs)."""
    return "doc_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def process(document_name: str, text: str, extractor: Extractor) -> ExtractionResult:
    doc_type = extractor.classify(text)
    fields = extractor.extract(text, doc_type)
    issues: list[ValidationIssue] = []
    data = None

    raw = {f.name: f.value for f in fields if f.value is not None}
    try:
        document = DOCUMENT_MODELS[doc_type].model_validate(raw)
    except ValidationError as exc:
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else "document"
            issues.append(
                ValidationIssue(
                    rule="schema",
                    severity="error",
                    message=f"{field}: {error['msg']}",
                    fields=[field],
                )
            )
    else:
        data = document.model_dump(mode="json")
        if isinstance(document, CertificateOfInsurance):
            issues += validate_coi(document)
        elif isinstance(document, LossRun):
            issues += validate_loss_run(document)

    if data is None:
        status = "rejected"
    elif issues or any(f.needs_review for f in fields):
        status = "needs_review"
    else:
        status = "accepted"

    return ExtractionResult(
        document_id=document_id_for(text),
        document_name=document_name,
        doc_type=doc_type,
        extractor=extractor.name,
        fields=fields,
        data=data,
        issues=issues,
        status=status,
    )
