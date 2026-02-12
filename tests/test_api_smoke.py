from __future__ import annotations

from app.models import DocumentStatus


def test_upload_status_and_document_smoke(client, fake_png_file, monkeypatch) -> None:
    def fake_process(db, document):
        document.status = DocumentStatus.processed
        document.document_type = "medical_bill"
        document.confidence_score = 0.92
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    monkeypatch.setattr("app.api.upload.process_document", fake_process)

    response = client.post("/api/upload", files={"file": fake_png_file})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    document_id = payload["document_id"]

    status = client.get(f"/api/upload/{document_id}/status")
    assert status.status_code == 200
    assert status.json()["document_type"] == "medical_bill"

    document = client.get(f"/api/documents/{document_id}")
    assert document.status_code == 200
    assert document.json()["id"] == document_id
