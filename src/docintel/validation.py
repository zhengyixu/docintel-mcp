"""Deterministic business rules applied after extraction, whatever the extractor.

These are the checks an LLM should never be trusted to do on its own:
arithmetic, date ordering, identifier formats.
"""

from __future__ import annotations

import re
from decimal import Decimal

from docintel.schemas import CertificateOfInsurance, LossRun, ValidationIssue

POLICY_NUMBER = re.compile(r"^[A-Z]{2,4}-?\d{6,10}$")
CENT = Decimal("0.01")


def _dates_in_order(effective, expiration) -> list[ValidationIssue]:
    if expiration <= effective:
        return [
            ValidationIssue(
                rule="policy_period_order",
                severity="error",
                message=f"Policy expiration {expiration} is not after effective date {effective}.",
                fields=["policy_effective", "policy_expiration"],
            )
        ]
    return []


def _policy_number(value: str) -> list[ValidationIssue]:
    if not POLICY_NUMBER.match(value):
        return [
            ValidationIssue(
                rule="policy_number_format",
                severity="warning",
                message=f"Policy number '{value}' does not match the expected format.",
                fields=["policy_number"],
            )
        ]
    return []


def validate_coi(doc: CertificateOfInsurance) -> list[ValidationIssue]:
    issues = _dates_in_order(doc.policy_effective, doc.policy_expiration)
    issues += _policy_number(doc.policy_number)
    if doc.each_occurrence_limit <= 0:
        issues.append(
            ValidationIssue(
                rule="limit_positive",
                severity="error",
                message="Each-occurrence limit must be greater than zero.",
                fields=["each_occurrence_limit"],
            )
        )
    if doc.general_aggregate_limit is not None and doc.general_aggregate_limit < doc.each_occurrence_limit:
        issues.append(
            ValidationIssue(
                rule="aggregate_at_least_occurrence",
                severity="warning",
                message="General aggregate limit is lower than the each-occurrence limit.",
                fields=["general_aggregate_limit", "each_occurrence_limit"],
            )
        )
    if doc.certificate_date > doc.policy_expiration:
        issues.append(
            ValidationIssue(
                rule="certificate_within_policy",
                severity="warning",
                message="Certificate was issued after the policy expired.",
                fields=["certificate_date", "policy_expiration"],
            )
        )
    return issues


def validate_loss_run(doc: LossRun) -> list[ValidationIssue]:
    issues = _dates_in_order(doc.policy_effective, doc.policy_expiration)
    issues += _policy_number(doc.policy_number)
    for claim in doc.claims:
        if abs(claim.paid + claim.reserve - claim.total_incurred) > CENT:
            issues.append(
                ValidationIssue(
                    rule="claim_incurred_arithmetic",
                    severity="error",
                    message=(
                        f"Claim {claim.claim_number}: paid {claim.paid} + reserve {claim.reserve} "
                        f"does not equal total incurred {claim.total_incurred}."
                    ),
                    fields=["claims"],
                )
            )
        if claim.loss_date > doc.valuation_date:
            issues.append(
                ValidationIssue(
                    rule="loss_before_valuation",
                    severity="error",
                    message=f"Claim {claim.claim_number}: loss date is after the valuation date.",
                    fields=["claims", "valuation_date"],
                )
            )
        if claim.status == "closed" and claim.reserve != 0:
            issues.append(
                ValidationIssue(
                    rule="closed_claim_reserve",
                    severity="warning",
                    message=f"Claim {claim.claim_number} is closed but still carries a reserve.",
                    fields=["claims"],
                )
            )
    claims_total = sum((c.total_incurred for c in doc.claims), Decimal("0"))
    if abs(claims_total - doc.total_incurred) > CENT:
        issues.append(
            ValidationIssue(
                rule="loss_run_total",
                severity="error",
                message=f"Stated total incurred {doc.total_incurred} does not match the sum of claims {claims_total}.",
                fields=["total_incurred", "claims"],
            )
        )
    return issues
