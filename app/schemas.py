from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Evidence / extraction primitives
# ---------------------------------------------------------------------------

class SourceBBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class SourceEvidence(BaseModel):
    quote: str | None = None
    bbox: SourceBBox | None = None
    page_number: int | None = None


class ExtractedField(BaseModel):
    value: str | float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[SourceEvidence] = Field(default_factory=list)


class LineItemExtraction(BaseModel):
    service: str | None = None
    code: str | None = None
    amount: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[SourceEvidence] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Type-specific extraction schemas
# ---------------------------------------------------------------------------

class InsuranceClaimExtraction(BaseModel):
    document_type: Literal["insurance_claim"]
    claim_number: ExtractedField
    claimant_name: ExtractedField
    date_of_service: ExtractedField
    total_amount: ExtractedField
    provider_name: ExtractedField
    policy_number: ExtractedField
    line_items: list[LineItemExtraction] = Field(default_factory=list)


class MedicalBillExtraction(BaseModel):
    document_type: Literal["medical_bill"]
    invoice_number: ExtractedField
    patient_name: ExtractedField
    date_of_service: ExtractedField
    total_amount: ExtractedField
    provider_name: ExtractedField
    line_items: list[LineItemExtraction] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# OCR schemas
# ---------------------------------------------------------------------------

class OCRWord(BaseModel):
    text: str
    confidence: float
    bbox: SourceBBox | None = None
    page_number: int


class OCRPage(BaseModel):
    page_number: int
    text: str
    words: list[OCRWord] = Field(default_factory=list)


class OCRResult(BaseModel):
    full_text: str
    pages: list[OCRPage]


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

class ExtractionResult(BaseModel):
    document_type: Literal["insurance_claim", "medical_bill"]
    fields: dict[str, ExtractedField]
    line_items: list[LineItemExtraction]
    raw_response: dict[str, Any] = Field(default_factory=dict)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: dict[str, ExtractedField]) -> dict[str, ExtractedField]:
        if not value:
            raise ValueError("fields cannot be empty")
        return value


# ---------------------------------------------------------------------------
# API response / request DTOs
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    document_id: str
    status: str
    document_type: str | None = None
    confidence_score: float | None = None

    @classmethod
    def from_document(cls, doc: Any) -> UploadResponse:
        return cls(
            document_id=doc.id,
            status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
            document_type=doc.document_type,
            confidence_score=doc.confidence_score,
        )


class DocumentSummary(BaseModel):
    """Shared base for document list items and review queue entries."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    status: str
    document_type: str | None
    confidence_score: float | None


class DocumentListItem(DocumentSummary):
    content_type: str
    created_at: datetime


class ReviewQueueItem(DocumentSummary):
    """Alias with document_id for backward-compatible JSON keys."""
    document_id: str = ""

    @classmethod
    def from_document(cls, doc: Any) -> ReviewQueueItem:
        return cls(
            id=doc.id,
            document_id=doc.id,
            original_filename=doc.original_filename,
            document_type=doc.document_type,
            confidence_score=doc.confidence_score,
            status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        )


class DocumentDetail(DocumentSummary):
    content_type: str
    file_path: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    extraction: dict[str, Any] | None = None


class ReviewUpdateRequest(BaseModel):
    extraction_data: dict[str, Any] | None = None
