"""Deterministic, regex-based extractor for plain-text documents.

Day 1: this is the stub that lets the MCP server work end to end.
Day 4: this is the "rules-only" baseline in the rules vs. LLM vs. hybrid
comparison, so keep it honest and do not tune it to the sample files.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from docintel.schemas import DocType, ExtractedField

EXACT = 0.95  # primary label matched
ALIAS = 0.70  # a looser alias matched: plausible, but a human should look
MISSING = 0.0

# field -> (primary label, [aliases])
COI_LABELS: dict[str, tuple[str, list[str]]] = {
    "certificate_date": ("Certificate Date", ["Date Issued", "Date"]),
    "insured_name": ("Insured", ["Named Insured"]),
    "producer_name": ("Producer", ["Agency", "Broker"]),
    "insurer_name": ("Insurer", ["Carrier", "Insurance Company"]),
    "policy_number": ("Policy Number", ["Policy No", "Policy #"]),
    "coverage_type": ("Coverage", ["Type of Insurance"]),
    "policy_effective": ("Policy Effective", ["Effective Date", "Eff"]),
    "policy_expiration": ("Policy Expiration", ["Expiration Date", "Exp"]),
    "each_occurrence_limit": ("Each Occurrence", ["Per Occurrence", "Occurrence Limit"]),
    "general_aggregate_limit": ("General Aggregate", ["Aggregate"]),
    "certificate_holder": ("Certificate Holder", ["Holder"]),
}

LOSS_RUN_LABELS: dict[str, tuple[str, list[str]]] = {
    "insured_name": ("Insured", ["Named Insured"]),
    "insurer_name": ("Insurer", ["Carrier", "Insurance Company"]),
    "policy_number": ("Policy Number", ["Policy No", "Policy #"]),
    "policy_effective": ("Policy Effective", ["Effective Date"]),
    "policy_expiration": ("Policy Expiration", ["Expiration Date"]),
    "valuation_date": ("Valuation Date", ["Valued As Of", "As Of"]),
    "total_incurred": ("Total Incurred", ["Grand Total", "Total"]),
}

DATE_FIELDS = {
    "certificate_date",
    "policy_effective",
    "policy_expiration",
    "valuation_date",
}
MONEY_FIELDS = {"each_occurrence_limit", "general_aggregate_limit", "total_incurred"}

# CLM-2025-0001 | 03/14/2025 | Closed | Rear-end collision | 12,500.00 | 0.00 | 12,500.00
CLAIM_ROW = re.compile(
    r"^\s*(?P<claim_number>[A-Z]{2,5}-[\w-]+)\s*\|\s*(?P<loss_date>[\d/.-]+)\s*\|"
    r"\s*(?P<status>open|closed)\s*\|\s*(?P<description>[^|]+?)\s*\|"
    r"\s*(?P<paid>[$\d,.]+)\s*\|\s*(?P<reserve>[$\d,.]+)\s*\|\s*(?P<total_incurred>[$\d,.]+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_date(raw: str) -> str | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_money(raw: str) -> str | None:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    try:
        return str(Decimal(cleaned))
    except InvalidOperation:
        return None


def _find(text: str, label: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", text, re.IGNORECASE | re.MULTILINE)
    return match.group(1) if match else None


def _normalize(name: str, raw: str) -> str | None:
    if name in DATE_FIELDS:
        return parse_date(raw)
    if name in MONEY_FIELDS:
        return parse_money(raw)
    return raw.strip() or None


def _labelled_fields(text: str, labels: dict[str, tuple[str, list[str]]]) -> list[ExtractedField]:
    fields: list[ExtractedField] = []
    for name, (primary, aliases) in labels.items():
        value, confidence = None, MISSING
        for label, score in [(primary, EXACT)] + [(a, ALIAS) for a in aliases]:
            raw = _find(text, label)
            if raw is None:
                continue
            value = _normalize(name, raw)
            # Found the label but could not parse the value: keep the raw text
            # for the reviewer and mark it as unusable.
            confidence = score if value is not None else 0.30
            value = value if value is not None else raw
            break
        fields.append(ExtractedField(name=name, value=value, confidence=confidence))
    return fields


def _claims_field(text: str) -> ExtractedField:
    claims = []
    confidence = EXACT
    for row in CLAIM_ROW.finditer(text):
        claim = row.groupdict()
        claim["status"] = claim["status"].lower()
        claim["loss_date"] = parse_date(claim["loss_date"]) or claim["loss_date"]
        for money in ("paid", "reserve", "total_incurred"):
            parsed = parse_money(claim[money])
            if parsed is None:
                confidence = 0.30
            claim[money] = parsed if parsed is not None else claim[money]
        claims.append(claim)
    if not claims:
        # "No claims" is a legitimate loss run, but only when the document says so.
        confidence = EXACT if re.search(r"no (claims|losses) reported", text, re.IGNORECASE) else 0.50
    return ExtractedField(name="claims", value=claims, confidence=confidence)


class RulesExtractor:
    name = "rules-v1"

    def classify(self, text: str) -> DocType:
        head = text[:400].lower()
        if "loss run" in head or CLAIM_ROW.search(text):
            return DocType.LOSS_RUN
        return DocType.COI

    def extract(self, text: str, doc_type: DocType) -> list[ExtractedField]:
        if doc_type is DocType.LOSS_RUN:
            return _labelled_fields(text, LOSS_RUN_LABELS) + [_claims_field(text)]
        return _labelled_fields(text, COI_LABELS)
