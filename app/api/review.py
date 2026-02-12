from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, DocumentStatus, ReviewState
from app.queries import get_document_or_404, get_latest_extraction_or_404
from app.schemas import ReviewQueueItem, ReviewUpdateRequest

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/queue", response_model=list[ReviewQueueItem])
def review_queue(db: Session = Depends(get_db)) -> list[ReviewQueueItem]:
    items = db.scalars(
        select(Document).where(Document.status == DocumentStatus.review_required).order_by(desc(Document.created_at))
    ).all()
    return [ReviewQueueItem.from_document(item) for item in items]


def _update_review_status(
    db: Session, document_id: str, doc_status: DocumentStatus, review_state: ReviewState, extraction_json: str = "",
) -> dict[str, str]:
    document = get_document_or_404(db, document_id)
    extraction = get_latest_extraction_or_404(db, document_id)

    if extraction_json.strip():
        payload = ReviewUpdateRequest(extraction_data=json.loads(extraction_json))
        extraction.extraction_data = payload.extraction_data or extraction.extraction_data

    extraction.review_state = review_state
    document.status = doc_status
    db.add_all([document, extraction])
    db.commit()
    return {"status": review_state.value, "document_id": document_id}


@router.post("/{document_id}/approve")
def approve_document(
    document_id: str,
    extraction_json: str = Form(default=""),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return _update_review_status(db, document_id, DocumentStatus.reviewed, ReviewState.approved, extraction_json)


@router.post("/{document_id}/reject")
def reject_document(document_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    return _update_review_status(db, document_id, DocumentStatus.rejected, ReviewState.rejected)
