from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ExtractedField, InsuranceClaimExtraction, MedicalBillExtraction


def test_insurance_claim_schema_validates() -> None:
    payload = InsuranceClaimExtraction(
        document_type="insurance_claim",
        claim_number=ExtractedField(value="CLM-123", confidence=0.93),
        claimant_name=ExtractedField(value="Jane Doe", confidence=0.88),
        date_of_service=ExtractedField(value="2025-05-10", confidence=0.8),
        total_amount=ExtractedField(value=1820.55, confidence=0.84),
        provider_name=ExtractedField(value="City Hospital", confidence=0.8),
        policy_number=ExtractedField(value="POL-777", confidence=0.9),
        line_items=[],
    )
    assert payload.claim_number.value == "CLM-123"


def test_medical_bill_schema_requires_invoice_number() -> None:
    with pytest.raises(ValidationError):
        MedicalBillExtraction(
            document_type="medical_bill",
            patient_name=ExtractedField(value="John Doe", confidence=0.9),
            date_of_service=ExtractedField(value="2024-01-01", confidence=0.8),
            total_amount=ExtractedField(value=200.0, confidence=0.7),
            provider_name=ExtractedField(value="Provider", confidence=0.7),
            line_items=[],
        )
