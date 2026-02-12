from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
from app.schemas import (
    ExtractedField,
    ExtractionResult,
    InsuranceClaimExtraction,
    LineItemExtraction,
    MedicalBillExtraction,
    OCRResult,
    SourceBBox,
    SourceEvidence,
)


def _detect_document_type(text: str) -> str:
    normalized = text.lower()
    insurance_signals = ["claim", "policy", "claimant", "insurance"]
    medical_signals = ["invoice", "cpt", "medical", "patient", "provider bill"]

    insurance_score = sum(token in normalized for token in insurance_signals)
    medical_score = sum(token in normalized for token in medical_signals)
    return "insurance_claim" if insurance_score >= medical_score else "medical_bill"


def _safe_amount(value: str | None) -> float | None:
    if not value:
        return None
    clean = re.sub(r"[^0-9.]", "", value)
    try:
        return float(clean) if clean else None
    except ValueError:
        return None


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


def _fallback_extraction(ocr: OCRResult) -> ExtractionResult:
    text = ocr.full_text
    doc_type = _detect_document_type(text)
    line_items = _extract_line_items_fallback(text)

    if doc_type == "insurance_claim":
        fields = {
            "claim_number": _field_from_regex(text, r"(?:claim\s*(?:number|#)?\s*[:\-]?\s*([A-Z0-9\-]+))"),
            "claimant_name": _field_from_regex(text, r"(?:claimant(?:\sname)?\s*[:\-]?\s*([A-Za-z ,.'-]+))"),
            "date_of_service": _field_from_regex(text, r"(?:date of service\s*[:\-]?\s*([0-9/\-]{6,12}))"),
            "total_amount": _field_from_regex(text, r"(?:total(?: amount)?\s*[:\-]?\s*(\$?[0-9,]+\.[0-9]{2}))"),
            "provider_name": _field_from_regex(text, r"(?:provider(?: name)?\s*[:\-]?\s*([A-Za-z0-9 ,.'-]+))"),
            "policy_number": _field_from_regex(text, r"(?:policy(?: number|#)?\s*[:\-]?\s*([A-Z0-9\-]+))"),
        }
    else:
        fields = {
            "invoice_number": _field_from_regex(text, r"(?:invoice(?: number|#)?\s*[:\-]?\s*([A-Z0-9\-]+))"),
            "patient_name": _field_from_regex(text, r"(?:patient(?: name)?\s*[:\-]?\s*([A-Za-z ,.'-]+))"),
            "date_of_service": _field_from_regex(text, r"(?:date of service\s*[:\-]?\s*([0-9/\-]{6,12}))"),
            "total_amount": _field_from_regex(text, r"(?:total(?: amount)?\s*[:\-]?\s*(\$?[0-9,]+\.[0-9]{2}))"),
            "provider_name": _field_from_regex(text, r"(?:provider(?: name)?\s*[:\-]?\s*([A-Za-z0-9 ,.'-]+))"),
        }

    amount_field = fields.get("total_amount")
    if amount_field and isinstance(amount_field.value, str):
        amount = _safe_amount(amount_field.value)
        fields["total_amount"] = ExtractedField(
            value=amount,
            confidence=amount_field.confidence if amount is not None else 0.2,
            evidence=amount_field.evidence,
        )

    return ExtractionResult(
        document_type=doc_type,
        fields=fields,
        line_items=line_items,
        raw_response={"mode": "fallback"},
    )


def _closest_word_evidence(quote: str, ocr: OCRResult) -> SourceEvidence | None:
    token = quote.split(":")[-1].strip().split(" ")[0]
    token_lower = token.lower()
    for page in ocr.pages:
        for word in page.words:
            if word.text.lower().strip(",:.$") == token_lower and word.bbox is not None:
                return SourceEvidence(
                    quote=quote,
                    bbox=SourceBBox(
                        x=word.bbox.x,
                        y=word.bbox.y,
                        width=word.bbox.width,
                        height=word.bbox.height,
                    ),
                    page_number=page.page_number,
                )
    return SourceEvidence(quote=quote, bbox=None, page_number=None)


def _coerce_field(raw_field: dict[str, Any], ocr: OCRResult) -> ExtractedField:
    quote = raw_field.get("quote")
    evidence: list[SourceEvidence] = []
    if quote:
        anchor = _closest_word_evidence(str(quote), ocr)
        if anchor is not None:
            evidence.append(anchor)
    return ExtractedField(
        value=raw_field.get("value"),
        confidence=float(raw_field.get("confidence", 0.0)),
        evidence=evidence,
    )


def _ensure_fields(fields: dict[str, ExtractedField], required: list[str]) -> dict[str, ExtractedField]:
    for name in required:
        fields.setdefault(name, ExtractedField(value=None, confidence=0.0, evidence=[]))
    return fields


def _extract_with_claude(ocr: OCRResult) -> ExtractionResult:
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
    prompt = """
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
    response = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1800,
        messages=[{"role": "user", "content": f"{prompt}\n\nOCR TEXT:\n{ocr.full_text[:12000]}"}],
    )

    text_blocks = [blk.text for blk in response.content if getattr(blk, "type", "") == "text"]
    payload_text = "\n".join(text_blocks).strip()
    cleaned = payload_text.removeprefix("```json").removesuffix("```").strip()
    payload = json.loads(cleaned)

    raw_fields = payload.get("fields", {})
    fields: dict[str, ExtractedField] = {}
    for key, value in raw_fields.items():
        fields[key] = _coerce_field(value, ocr)

    line_items: list[LineItemExtraction] = []
    for row in payload.get("line_items", []):
        quote = row.get("quote")
        evidence = [_closest_word_evidence(str(quote), ocr)] if quote else []
        line_items.append(
            LineItemExtraction(
                service=row.get("service"),
                code=row.get("code"),
                amount=_safe_amount(str(row.get("amount"))) if row.get("amount") is not None else None,
                confidence=float(row.get("confidence", 0.0)),
                evidence=[ev for ev in evidence if ev is not None],
            )
        )

    return ExtractionResult(
        document_type=payload.get("document_type", _detect_document_type(ocr.full_text)),
        fields=fields,
        line_items=line_items,
        raw_response=payload,
    )


def validate_type_specific(result: ExtractionResult) -> ExtractionResult:
    if result.document_type == "insurance_claim":
        fields = _ensure_fields(
            result.fields,
            ["claim_number", "claimant_name", "date_of_service", "total_amount", "provider_name", "policy_number"],
        )
        InsuranceClaimExtraction(
            document_type="insurance_claim",
            claim_number=fields["claim_number"],
            claimant_name=fields["claimant_name"],
            date_of_service=fields["date_of_service"],
            total_amount=fields["total_amount"],
            provider_name=fields["provider_name"],
            policy_number=fields["policy_number"],
            line_items=result.line_items,
        )
        result.fields = fields
        return result

    fields = _ensure_fields(
        result.fields, ["invoice_number", "patient_name", "date_of_service", "total_amount", "provider_name"]
    )
    MedicalBillExtraction(
        document_type="medical_bill",
        invoice_number=fields["invoice_number"],
        patient_name=fields["patient_name"],
        date_of_service=fields["date_of_service"],
        total_amount=fields["total_amount"],
        provider_name=fields["provider_name"],
        line_items=result.line_items,
    )
    result.fields = fields
    return result


def extract_structured_data(ocr: OCRResult) -> ExtractionResult:
    result = _extract_with_claude(ocr) if settings.anthropic_api_key else _fallback_extraction(ocr)
    return validate_type_specific(result)
