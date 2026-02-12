from __future__ import annotations

from app.schemas import ExtractedField, ExtractionResult, LineItemExtraction
from app.processors.pipeline import _has_missing_critical, compute_document_confidence


def test_confidence_scoring_uses_fields_and_line_items() -> None:
    result = ExtractionResult(
        document_type="insurance_claim",
        fields={
            "claim_number": ExtractedField(value="CLM-1", confidence=0.9),
            "claimant_name": ExtractedField(value="Alice", confidence=0.8),
            "date_of_service": ExtractedField(value="2025-02-10", confidence=0.95),
            "total_amount": ExtractedField(value=500.0, confidence=0.85),
            "provider_name": ExtractedField(value="Provider", confidence=0.8),
            "policy_number": ExtractedField(value="POL-1", confidence=0.9),
        },
        line_items=[LineItemExtraction(service="Lab", code="80050", amount=100.0, confidence=0.75)],
        raw_response={},
    )
    score = compute_document_confidence(result)
    assert 0.0 <= score <= 1.0
    assert score > 0.7


def test_missing_critical_fields_triggers_review() -> None:
    result = ExtractionResult(
        document_type="medical_bill",
        fields={
            "invoice_number": ExtractedField(value=None, confidence=0.1),
            "patient_name": ExtractedField(value="Bob", confidence=0.8),
            "date_of_service": ExtractedField(value="2025-01-01", confidence=0.8),
            "total_amount": ExtractedField(value=123.0, confidence=0.8),
            "provider_name": ExtractedField(value="Clinic", confidence=0.8),
        },
        line_items=[],
        raw_response={},
    )
    assert _has_missing_critical(result) is True
