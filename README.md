# Document Intake POC

Local FastAPI service for multimodal document intake of insurance claims and medical bills.

## Features

- Upload PDF/JPG/PNG documents
- OCR extraction with Tesseract and bounding boxes
- Structured extraction with Anthropic Claude (with fallback extraction)
- Type-specific validation for insurance claims and medical bills
- Confidence scoring with review queue threshold
- HTMX-based review UI with source quote and bbox context

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy env file:

   ```bash
   cp .env.example .env
   ```

4. Ensure Tesseract OCR is installed on the machine and available on `PATH`.
5. Run server:

   ```bash
   uvicorn app.main:app --reload
   ```

## API Endpoints

- `POST /api/upload` - Upload and process document
- `GET /api/upload/{document_id}/status` - Processing status
- `GET /api/documents` - List documents
- `GET /api/documents/{document_id}` - Document details + extraction
- `GET /api/review/queue` - Review queue JSON
- `GET /api/review/ui` - Review queue UI
- `POST /api/review/{document_id}/approve` - Approve extraction
- `POST /api/review/{document_id}/reject` - Reject extraction

## Tests

Run:

```bash
pytest
```
