"""Typed schemas for the two document types and for extraction results.

The document models (CertificateOfInsurance, LossRun) are the contract:
- the rules extractor fills them today,
- on day 2 the same models become the JSON schema handed to the LLM for
  structured output, so every extractor is held to one definition.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

# Fields below this confidence are routed to a human reviewer.
REVIEW_THRESHOLD = 0.80


class DocType(StrEnum):
    COI = "certificate_of_insurance"
    LOSS_RUN = "loss_run"


class CertificateOfInsurance(BaseModel):
    certificate_date: date
    insured_name: str
    producer_name: str
    insurer_name: str
    policy_number: str
    coverage_type: str
    policy_effective: date
    policy_expiration: date
    each_occurrence_limit: Decimal
    general_aggregate_limit: Decimal | None = None
    certificate_holder: str | None = None


class Claim(BaseModel):
    claim_number: str
    loss_date: date
    status: Literal["open", "closed"]
    description: str
    paid: Decimal
    reserve: Decimal
    total_incurred: Decimal


class LossRun(BaseModel):
    insured_name: str
    insurer_name: str
    policy_number: str
    policy_effective: date
    policy_expiration: date
    valuation_date: date
    claims: list[Claim]
    total_incurred: Decimal


DOCUMENT_MODELS: dict[DocType, type[BaseModel]] = {
    DocType.COI: CertificateOfInsurance,
    DocType.LOSS_RUN: LossRun,
}


class ExtractedField(BaseModel):
    """One raw field as an extractor produced it, before validation."""

    name: str
    value: Any | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["rules", "ocr", "llm"] = "rules"

    @property
    def needs_review(self) -> bool:
        return self.confidence < REVIEW_THRESHOLD


class ValidationIssue(BaseModel):
    rule: str
    severity: Literal["error", "warning"]
    message: str
    fields: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    document_id: str
    document_name: str
    doc_type: DocType
    extractor: str
    fields: list[ExtractedField]
    # Normalized, schema-valid data. None when the fields do not fit the schema.
    data: dict[str, Any] | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    status: Literal["accepted", "needs_review", "rejected"]

    def low_confidence_fields(self) -> list[ExtractedField]:
        return [f for f in self.fields if f.needs_review]
