from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.document_types import critical_field_names
from app.models import Document, DocumentStatus, Extraction, FieldEvidence, LineItem, ReviewState
from app.processors.extractor import extract_structured_data
from app.processors.ocr import run_ocr
from app.schemas import ExtractedField, ExtractionResult


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _score_field(field: ExtractedField) -> float:
    if field.value in (None, "", []):
        return 0.0
    return field.confidence


def compute_document_confidence(result: ExtractionResult) -> float:
    field_scores = [_score_field(f) for f in result.fields.values()]
    line_item_scores = [row.confidence for row in result.line_items] or [0.5]

    weighted = (sum(field_scores) / max(len(field_scores), 1)) * 0.8 + (
        sum(line_item_scores) / max(len(line_item_scores), 1)
    ) * 0.2
    return round(max(min(weighted, 1.0), 0.0), 4)


def _has_missing_critical(result: ExtractionResult) -> bool:
    for name in critical_field_names(result.document_type):
        field = result.fields.get(name)
        if field is None or field.value in (None, ""):
            return True
    return False


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _next_extraction_version(db: Session, document_id: str) -> int:
    current = db.scalar(select(func.max(Extraction.version)).where(Extraction.document_id == document_id))
    return (current or 0) + 1


def _persist_snapshot(directory: str, document_id: str, payload: dict) -> None:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{document_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _save_field_evidences(db: Session, extraction_id: int, result: ExtractionResult) -> None:
    for field_name, field in result.fields.items():
        evidences = field.evidence or [None]
        for ev in evidences:
            db.add(FieldEvidence(
                extraction_id=extraction_id,
                field_name=field_name,
                field_value=None if field.value is None else str(field.value),
                confidence=field.confidence,
                quote=ev.quote if ev else None,
                bbox=ev.bbox.model_dump() if ev and ev.bbox else None,
                page_number=ev.page_number if ev else None,
            ))


def _save_line_items(db: Session, extraction_id: int, result: ExtractionResult) -> None:
    for idx, row in enumerate(result.line_items):
        ev = row.evidence[0] if row.evidence else None
        db.add(LineItem(
            extraction_id=extraction_id,
            row_index=idx,
            service=row.service,
            code=row.code,
            amount=row.amount,
            confidence=row.confidence,
            evidence_quote=ev.quote if ev else None,
            evidence_bbox=ev.bbox.model_dump() if ev and ev.bbox else None,
            page_number=ev.page_number if ev else None,
        ))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

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

        _save_field_evidences(db, extraction_model.id, extraction_result)
        _save_line_items(db, extraction_model.id, extraction_result)

        _persist_snapshot(settings.ocr_dir, document.id, ocr_result.model_dump(mode="json"))
        _persist_snapshot(settings.extraction_dir, document.id, extraction_result.model_dump(mode="json"))

        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:  # pragma: no cover
        document.status = DocumentStatus.failed
        document.error_message = str(exc)
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
