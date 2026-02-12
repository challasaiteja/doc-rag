from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    processed = "processed"
    review_required = "review_required"
    reviewed = "reviewed"
    rejected = "rejected"
    failed = "failed"


class ReviewState(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, native_enum=False),
        default=DocumentStatus.uploaded,
        nullable=False,
    )
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    extraction_records: Mapped[list["Extraction"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    review_state: Mapped[ReviewState] = mapped_column(
        SQLEnum(ReviewState, native_enum=False),
        default=ReviewState.pending,
        nullable=False,
    )
    extraction_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="extraction_records")
    field_evidences: Mapped[list["FieldEvidence"]] = relationship(
        back_populates="extraction", cascade="all, delete-orphan"
    )
    line_items: Mapped[list["LineItem"]] = relationship(back_populates="extraction", cascade="all, delete-orphan")


class FieldEvidence(Base):
    __tablename__ = "field_evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    extraction_id: Mapped[int] = mapped_column(Integer, ForeignKey("extractions.id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    extraction: Mapped[Extraction] = relationship(back_populates="field_evidences")


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    extraction_id: Mapped[int] = mapped_column(Integer, ForeignKey("extractions.id"), nullable=False, index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    service: Mapped[str | None] = mapped_column(String(255), nullable=True)
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_bbox: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    extraction: Mapped[Extraction] = relationship(back_populates="line_items")
