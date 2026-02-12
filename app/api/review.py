from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Document, DocumentStatus, Extraction, ReviewState
from app.schemas import ReviewQueueItem, ReviewUpdateRequest

router = APIRouter(prefix="/api/review", tags=["review"])
templates = Jinja2Templates(directory="app/templates")


def _latest_extraction(db: Session, document_id: str) -> Extraction | None:
    return db.scalar(
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(desc(Extraction.version), desc(Extraction.id))
    )


@router.get("/queue", response_model=list[ReviewQueueItem])
def review_queue(db: Session = Depends(get_db)) -> list[ReviewQueueItem]:
    items = db.scalars(
        select(Document).where(Document.status == DocumentStatus.review_required).order_by(desc(Document.created_at))
    ).all()
    return [
        ReviewQueueItem(
            document_id=item.id,
            original_filename=item.original_filename,
            document_type=item.document_type,
            confidence_score=item.confidence_score,
            status=item.status.value,
        )
        for item in items
    ]


def _highlight_text(raw_text: str, quotes: list[str]) -> str:
    highlighted = raw_text
    for quote in sorted({q for q in quotes if q}, key=len, reverse=True):
        highlighted = highlighted.replace(quote, f"<mark>{quote}</mark>")
    return highlighted


@router.get("/ui", response_class=HTMLResponse)
def review_ui(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    candidate = db.scalar(
        select(Document).where(Document.status == DocumentStatus.review_required).order_by(desc(Document.created_at))
    )
    if candidate is None:
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context={"document": None, "extraction": None, "highlighted_text": "", "threshold": settings.confidence_threshold},
        )

    extraction = _latest_extraction(db, candidate.id)
    if extraction is None:
        raise HTTPException(status_code=500, detail="Extraction missing for review document")

    ocr_path = Path(settings.ocr_dir) / f"{candidate.id}.json"
    ocr_payload = {}
    if ocr_path.exists():
        import json

        ocr_payload = json.loads(ocr_path.read_text(encoding="utf-8"))

    full_text = ocr_payload.get("full_text", "")
    field_quotes: list[str] = []
    for field in extraction.extraction_data.get("fields", {}).values():
        for evidence in field.get("evidence", []):
            quote = evidence.get("quote")
            if quote:
                field_quotes.append(quote)

    highlighted_text = _highlight_text(full_text, field_quotes)
    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context={
            "document": candidate,
            "extraction": extraction.extraction_data,
            "highlighted_text": highlighted_text,
            "threshold": settings.confidence_threshold,
        },
    )


@router.post("/{document_id}/approve")
def approve_document(
    document_id: str,
    extraction_json: str = Form(default=""),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    extraction = _latest_extraction(db, document_id)
    if extraction is None:
        raise HTTPException(status_code=404, detail="Extraction not found")

    if extraction_json.strip():
        import json

        payload = ReviewUpdateRequest(extraction_data=json.loads(extraction_json))
        extraction.extraction_data = payload.extraction_data or extraction.extraction_data

    extraction.review_state = ReviewState.approved
    document.status = DocumentStatus.reviewed
    db.add_all([document, extraction])
    db.commit()
    return {"status": "approved", "document_id": document_id}


@router.post("/{document_id}/reject")
def reject_document(document_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    extraction = _latest_extraction(db, document_id)
    if extraction is None:
        raise HTTPException(status_code=404, detail="Extraction not found")

    extraction.review_state = ReviewState.rejected
    document.status = DocumentStatus.rejected
    db.add_all([document, extraction])
    db.commit()
    return {"status": "rejected", "document_id": document_id}
