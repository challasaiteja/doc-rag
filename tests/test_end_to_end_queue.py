from __future__ import annotations

import io

from app.schemas import OCRPage, OCRResult


def test_end_to_end_insurance_and_medical_documents(client, monkeypatch) -> None:
    insurance_text = """
    Insurance Claim
    Claim Number: CLM-9001
    Claimant: Alice Adams
    Date of Service: 01/05/2026
    Provider: Valley Clinic
    Policy Number: POL-222
    Total Amount: $1200.00
    """
    medical_text = """
    Medical Bill
    Invoice Number: INV-442
    Patient Name: Bob Baker
    Date of Service: 01/09/2026
    Provider Name: Care Hospital
    Total Amount: $350.00
    """

    state = {"count": 0}

    def fake_run_ocr(_path: str) -> OCRResult:
        state["count"] += 1
        text = insurance_text if state["count"] == 1 else medical_text
        return OCRResult(full_text=text, pages=[OCRPage(page_number=1, text=text, words=[])])

    monkeypatch.setattr("app.processors.pipeline.run_ocr", fake_run_ocr)

    resp1 = client.post("/api/upload", files={"file": ("insurance.png", io.BytesIO(b"img"), "image/png")})
    assert resp1.status_code == 200
    assert resp1.json()["document_type"] == "insurance_claim"

    resp2 = client.post("/api/upload", files={"file": ("medical.png", io.BytesIO(b"img"), "image/png")})
    assert resp2.status_code == 200
    assert resp2.json()["document_type"] == "medical_bill"

    all_docs = client.get("/api/documents")
    assert all_docs.status_code == 200
    assert len(all_docs.json()) == 2
