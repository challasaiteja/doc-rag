from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class UploadResponse(BaseModel):
    document_id: str
    status: str
    document_type: str | None = None
    confidence_score: float | None = None


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    content_type: str
    status: str
    document_type: str | None
    confidence_score: float | None
    created_at: datetime


class DocumentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    content_type: str
    status: str
    file_path: str
    document_type: str | None
    confidence_score: float | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    extraction: dict[str, Any] | None = None


class ReviewUpdateRequest(BaseModel):
    extraction_data: dict[str, Any] | None = None


class ReviewQueueItem(BaseModel):
    document_id: str
    original_filename: str
    document_type: str | None
    confidence_score: float | None
    status: str
