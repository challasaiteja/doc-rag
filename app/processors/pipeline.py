from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentStatus, Extraction, FieldEvidence, LineItem, ReviewState
from app.processors.extractor import extract_structured_data
from app.processors.ocr import run_ocr
from app.schemas import ExtractedField, ExtractionResult


CRITICAL_FIELDS_BY_TYPE: dict[str, list[str]] = {
    "insurance_claim": ["claim_number", "date_of_service", "total_amount"],
    "medical_bill": ["invoice_number", "date_of_service", "total_amount"],
}


def _score_field(field: ExtractedField) -> float:
    if field.value in (None, "", []):
        return 0.0
    return field.confidence


def compute_document_confidence(result: ExtractionResult) -> float:
    field_scores = [_score_field(field) for field in result.fields.values()]
    line_item_scores = [row.confidence for row in result.line_items] or [0.5]

    weighted = (sum(field_scores) / max(len(field_scores), 1)) * 0.8 + (
        sum(line_item_scores) / max(len(line_item_scores), 1)
    ) * 0.2
    return round(max(min(weighted, 1.0), 0.0), 4)


def _has_missing_critical(result: ExtractionResult) -> bool:
    for field_name in CRITICAL_FIELDS_BY_TYPE[result.document_type]:
        field = result.fields.get(field_name)
        if field is None or field.value in (None, ""):
            return True
    return False


def _next_extraction_version(db: Session, document_id: str) -> int:
    stmt = select(func.max(Extraction.version)).where(Extraction.document_id == document_id)
    current = db.scalar(stmt)
    return (current or 0) + 1


def _persist_ocr_snapshot(document_id: str, ocr_payload: dict) -> None:
    target = Path(settings.ocr_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{document_id}.json").write_text(json.dumps(ocr_payload, indent=2), encoding="utf-8")


def _persist_extraction_snapshot(document_id: str, extraction_payload: dict) -> None:
    target = Path(settings.extraction_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{document_id}.json").write_text(json.dumps(extraction_payload, indent=2), encoding="utf-8")


def process_document(db: Session, document: Document) -> Document:
    try:
        ocr_result = run_ocr(document.file_path)
        extraction_result = extract_structured_data(ocr_result)
        confidence = compute_document_confidence(extraction_result)
        review_required = confidence < settings.confidence_threshold or _has_missing_critical(extraction_result)

        document.document_type = extraction_result.document_type
        document.confidence_score = confidence
        document.status = DocumentStatus.review_required if review_required else DocumentStatus.processed
        document.error_message = None

        extraction_model = Extraction(
            document_id=document.id,
            version=_next_extraction_version(db, document.id),
            review_state=ReviewState.pending if review_required else ReviewState.approved,
            extraction_data=extraction_result.model_dump(mode="json"),
        )
        db.add(extraction_model)
        db.flush()

        for field_name, field in extraction_result.fields.items():
            for evidence in field.evidence or [None]:
                db.add(
                    FieldEvidence(
                        extraction_id=extraction_model.id,
                        field_name=field_name,
                        field_value=None if field.value is None else str(field.value),
                        confidence=field.confidence,
                        quote=evidence.quote if evidence else None,
                        bbox=evidence.bbox.model_dump() if evidence and evidence.bbox else None,
                        page_number=evidence.page_number if evidence else None,
                    )
                )

        for idx, row in enumerate(extraction_result.line_items):
            first_evidence = row.evidence[0] if row.evidence else None
            db.add(
                LineItem(
                    extraction_id=extraction_model.id,
                    row_index=idx,
                    service=row.service,
                    code=row.code,
                    amount=row.amount,
                    confidence=row.confidence,
                    evidence_quote=first_evidence.quote if first_evidence else None,
                    evidence_bbox=first_evidence.bbox.model_dump() if first_evidence and first_evidence.bbox else None,
                    page_number=first_evidence.page_number if first_evidence else None,
                )
            )

        _persist_ocr_snapshot(document.id, ocr_result.model_dump(mode="json"))
        _persist_extraction_snapshot(document.id, extraction_result.model_dump(mode="json"))

        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:  # pragma: no cover - defensive persistence
        document.status = DocumentStatus.failed
        document.error_message = str(exc)
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
