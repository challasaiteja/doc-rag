from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, Extraction
from app.schemas import DocumentDetail, DocumentListItem

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=list[DocumentListItem])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentListItem]:
    documents = db.scalars(select(Document).order_by(desc(Document.created_at))).all()
    return [DocumentListItem.model_validate(doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentDetail:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    extraction = db.scalar(
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(desc(Extraction.version), desc(Extraction.id))
    )
    payload = DocumentDetail.model_validate(document)
    payload.extraction = extraction.extraction_data if extraction else None
    return payload
