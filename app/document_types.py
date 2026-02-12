"""Single registry for document-type field definitions.

Used by extractor (fallback regex + validation) and pipeline (critical field checks).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldDef:
    name: str
    regex: str
    critical: bool = False


FIELD_REGISTRY: dict[str, list[FieldDef]] = {
    "insurance_claim": [
        FieldDef("claim_number", r"(?:claim\s*(?:number|#)?\s*[:\-]?\s*([A-Z0-9\-]+))", critical=True),
        FieldDef("claimant_name", r"(?:claimant(?:\sname)?\s*[:\-]?\s*([A-Za-z ,.'-]+))"),
        FieldDef("date_of_service", r"(?:date of service\s*[:\-]?\s*([0-9/\-]{6,12}))", critical=True),
        FieldDef("total_amount", r"(?:total(?: amount)?\s*[:\-]?\s*(\$?[0-9,]+\.[0-9]{2}))", critical=True),
        FieldDef("provider_name", r"(?:provider(?: name)?\s*[:\-]?\s*([A-Za-z0-9 ,.'-]+))"),
        FieldDef("policy_number", r"(?:policy(?: number|#)?\s*[:\-]?\s*([A-Z0-9\-]+))"),
    ],
    "medical_bill": [
        FieldDef("invoice_number", r"(?:invoice(?: number|#)?\s*[:\-]?\s*([A-Z0-9\-]+))", critical=True),
        FieldDef("patient_name", r"(?:patient(?: name)?\s*[:\-]?\s*([A-Za-z ,.'-]+))"),
        FieldDef("date_of_service", r"(?:date of service\s*[:\-]?\s*([0-9/\-]{6,12}))", critical=True),
        FieldDef("total_amount", r"(?:total(?: amount)?\s*[:\-]?\s*(\$?[0-9,]+\.[0-9]{2}))", critical=True),
        FieldDef("provider_name", r"(?:provider(?: name)?\s*[:\-]?\s*([A-Za-z0-9 ,.'-]+))"),
    ],
}


def required_field_names(doc_type: str) -> list[str]:
    return [f.name for f in FIELD_REGISTRY[doc_type]]


def critical_field_names(doc_type: str) -> list[str]:
    return [f.name for f in FIELD_REGISTRY[doc_type] if f.critical]
