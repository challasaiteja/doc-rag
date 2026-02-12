from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Document, Extraction


def get_document_or_404(db: Session, document_id: str) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def get_latest_extraction(db: Session, document_id: str) -> Extraction | None:
    return db.scalar(
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(desc(Extraction.version), desc(Extraction.id))
    )


def get_latest_extraction_or_404(db: Session, document_id: str) -> Extraction:
    extraction = get_latest_extraction(db, document_id)
    if extraction is None:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return extraction
