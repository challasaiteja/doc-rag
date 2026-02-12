from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document
from app.queries import get_document_or_404, get_latest_extraction
from app.schemas import DocumentDetail, DocumentListItem

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=list[DocumentListItem])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentListItem]:
    documents = db.scalars(select(Document).order_by(desc(Document.created_at))).all()
    return [DocumentListItem.model_validate(doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentDetail:
    document = get_document_or_404(db, document_id)
    extraction = get_latest_extraction(db, document_id)
    payload = DocumentDetail.model_validate(document)
    payload.extraction = extraction.extraction_data if extraction else None
    return payload
