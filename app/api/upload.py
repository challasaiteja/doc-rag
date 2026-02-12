from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Document
from app.processors.pipeline import process_document
from app.queries import get_document_or_404
from app.schemas import UploadResponse

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


def _save_upload(file: UploadFile) -> str:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    target_dir = Path(settings.upload_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid4()}{ext}"
    with target_path.open("wb") as out_file:
        out_file.write(file.file.read())
    return str(target_path)


@router.post("", response_model=UploadResponse)
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    file_path = _save_upload(file)
    document = Document(
        original_filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        file_path=file_path,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    processed = process_document(db, document)
    return UploadResponse.from_document(processed)


@router.get("/{document_id}/status", response_model=UploadResponse)
def upload_status(document_id: str, db: Session = Depends(get_db)) -> UploadResponse:
    return UploadResponse.from_document(get_document_or_404(db, document_id))
