from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
from app.document_types import FIELD_REGISTRY, required_field_names
from app.schemas import (
    ExtractedField,
    ExtractionResult,
    LineItemExtraction,
    OCRResult,
    SourceBBox,
    SourceEvidence,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

INSURANCE_SIGNALS = ["claim", "policy", "claimant", "insurance"]
MEDICAL_SIGNALS = ["invoice", "cpt", "medical", "patient", "provider bill"]


def _detect_document_type(text: str) -> str:
    normalized = text.lower()
    ins = sum(token in normalized for token in INSURANCE_SIGNALS)
    med = sum(token in normalized for token in MEDICAL_SIGNALS)
    return "insurance_claim" if ins >= med else "medical_bill"


def _safe_amount(value: str | None) -> float | None:
    if not value:
        return None
    clean = re.sub(r"[^0-9.]", "", value)
    try:
        return float(clean) if clean else None
    except ValueError:
        return None


def _closest_word_evidence(quote: str, ocr: OCRResult) -> SourceEvidence:
    token = quote.split(":")[-1].strip().split(" ")[0].lower()
    for page in ocr.pages:
        for word in page.words:
            if word.text.lower().strip(",:.$") == token and word.bbox is not None:
                return SourceEvidence(
                    quote=quote,
                    bbox=SourceBBox(x=word.bbox.x, y=word.bbox.y, width=word.bbox.width, height=word.bbox.height),
                    page_number=page.page_number,
                )
    return SourceEvidence(quote=quote, bbox=None, page_number=None)


def _ensure_fields(fields: dict[str, ExtractedField], doc_type: str) -> dict[str, ExtractedField]:
    for name in required_field_names(doc_type):
        fields.setdefault(name, ExtractedField(value=None, confidence=0.0, evidence=[]))
    return fields


# ---------------------------------------------------------------------------
# Fallback (regex) extraction
# ---------------------------------------------------------------------------

def _field_from_regex(text: str, pattern: str, confidence: float = 0.55) -> ExtractedField:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return ExtractedField(value=None, confidence=0.2, evidence=[])
    quote = match.group(0).strip()
    value = match.group(1).strip() if match.lastindex else quote
    return ExtractedField(
        value=value,
        confidence=confidence,
        evidence=[SourceEvidence(quote=quote, bbox=None, page_number=None)],
    )


def _extract_line_items_fallback(text: str) -> list[LineItemExtraction]:
    rows: list[LineItemExtraction] = []
    pattern = re.compile(r"([A-Za-z][A-Za-z0-9\s\-]{2,40})\s+([A-Z0-9]{3,12})\s+\$?([0-9]+\.[0-9]{2})")
    for match in pattern.finditer(text):
        rows.append(
            LineItemExtraction(
                service=match.group(1).strip(),
                code=match.group(2).strip(),
                amount=float(match.group(3)),
                confidence=0.5,
                evidence=[SourceEvidence(quote=match.group(0), bbox=None, page_number=None)],
            )
        )
        if len(rows) >= 20:
            break
    return rows


def _coerce_total_amount(fields: dict[str, ExtractedField]) -> None:
    amount_field = fields.get("total_amount")
    if amount_field and isinstance(amount_field.value, str):
        amount = _safe_amount(amount_field.value)
        fields["total_amount"] = ExtractedField(
            value=amount,
            confidence=amount_field.confidence if amount is not None else 0.2,
            evidence=amount_field.evidence,
        )


def _fallback_extraction(ocr: OCRResult) -> ExtractionResult:
    text = ocr.full_text
    doc_type = _detect_document_type(text)
    fields = {fd.name: _field_from_regex(text, fd.regex) for fd in FIELD_REGISTRY[doc_type]}
    _coerce_total_amount(fields)
    return ExtractionResult(
        document_type=doc_type,
        fields=fields,
        line_items=_extract_line_items_fallback(text),
        raw_response={"mode": "fallback"},
    )


# ---------------------------------------------------------------------------
# OpenAI extraction
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """
You are extracting structured data from OCR output of either an insurance claim or medical bill.
Return JSON only with this format:
{
  "document_type": "insurance_claim|medical_bill",
  "fields": {
    "<field_name>": {"value": "...", "confidence": 0.0-1.0, "quote": "short source text"}
  },
  "line_items": [
    {"service": "...", "code": "...", "amount": 0.0, "confidence": 0.0-1.0, "quote": "short source text"}
  ]
}
Use field names:
- insurance_claim: claim_number, claimant_name, date_of_service, total_amount, provider_name, policy_number
- medical_bill: invoice_number, patient_name, date_of_service, total_amount, provider_name
"""


def _coerce_field(raw_field: dict[str, Any], ocr: OCRResult) -> ExtractedField:
    quote = raw_field.get("quote")
    evidence = [_closest_word_evidence(str(quote), ocr)] if quote else []
    return ExtractedField(
        value=raw_field.get("value"),
        confidence=float(raw_field.get("confidence", 0.0)),
        evidence=evidence,
    )


def _coerce_line_item(row: dict[str, Any], ocr: OCRResult) -> LineItemExtraction:
    quote = row.get("quote")
    evidence = [_closest_word_evidence(str(quote), ocr)] if quote else []
    return LineItemExtraction(
        service=row.get("service"),
        code=row.get("code"),
        amount=_safe_amount(str(row.get("amount"))) if row.get("amount") is not None else None,
        confidence=float(row.get("confidence", 0.0)),
        evidence=evidence,
    )


def _extract_with_openai(ocr: OCRResult) -> ExtractionResult:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "You extract structured medical and insurance fields."},
            {"role": "user", "content": f"{EXTRACTION_PROMPT}\n\nOCR TEXT:\n{ocr.full_text[:12000]}"},
        ],
        temperature=0.0,
    )

    payload_text = (response.choices[0].message.content or "").strip()
    cleaned = payload_text.removeprefix("```json").removesuffix("```").strip()
    payload = json.loads(cleaned)

    fields = {key: _coerce_field(val, ocr) for key, val in payload.get("fields", {}).items()}
    line_items = [_coerce_line_item(row, ocr) for row in payload.get("line_items", [])]

    return ExtractionResult(
        document_type=payload.get("document_type", _detect_document_type(ocr.full_text)),
        fields=fields,
        line_items=line_items,
        raw_response=payload,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_structured_data(ocr: OCRResult) -> ExtractionResult:
    result = _extract_with_openai(ocr) if settings.openai_api_key else _fallback_extraction(ocr)
    result.fields = _ensure_fields(result.fields, result.document_type)
    return result
