# Document Intake POC

Local document processing system for insurance claims and medical bills. Extracts structured fields from PDFs and images using OCR + OpenAI, scores confidence per field, and routes low-confidence documents to a review queue.

## How it works

```
Upload (PDF/JPG/PNG)
  -> Tesseract OCR (text + word bounding boxes)
  -> OpenAI extraction (or regex fallback if no API key)
  -> Type-specific validation (insurance claim vs medical bill)
  -> Confidence scoring (field-level + document-level)
  -> If confidence < 0.8 or critical fields missing -> Review Queue
  -> Otherwise -> Auto-approved
```

## Tech stack

- **FastAPI** - REST API backend
- **SQLite** - local database (via SQLAlchemy)
- **Tesseract** - OCR with bounding box extraction
- **OpenAI API** - structured field extraction (falls back to regex if no key)
- **Streamlit** - upload and review UI
- **Pydantic** - schema validation

## Project structure

```
app/
  main.py              # FastAPI app setup and lifespan
  config.py            # Settings loaded from .env
  database.py          # SQLAlchemy engine and session
  models.py            # Document, Extraction, FieldEvidence, LineItem
  schemas.py           # Pydantic DTOs (extraction, API responses)
  queries.py           # Shared DB query helpers
  document_types.py    # Field registry per document type
  api/
    upload.py          # POST /api/upload, GET /api/upload/{id}/status
    documents.py       # GET /api/documents, GET /api/documents/{id}
    review.py          # GET /api/review/queue, POST approve/reject
  processors/
    ocr.py             # Tesseract OCR with bbox extraction
    extractor.py       # OpenAI extraction + regex fallback
    pipeline.py        # Orchestrates OCR -> extract -> score -> persist
streamlit_app.py       # Streamlit UI (upload, review queue, documents)
tests/                 # Schema, pipeline, API, and end-to-end tests
storage/               # Runtime file storage (gitignored)
```

## Setup

### Prerequisites

- Python 3.11+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on `PATH`

### Install and run

```bash
# 1. Create virtual environment
python3 -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY (optional - regex fallback works without it)

# 4. Start the API server
uvicorn app.main:app --reload

# 5. In a second terminal, start the UI
streamlit run streamlit_app.py
```

The API runs at `http://127.0.0.1:8000` (Swagger docs at `/docs`).
The Streamlit UI runs at `http://localhost:8501`.

## Supported document types

| Type | Fields extracted |
|---|---|
| Insurance claim | claim_number, claimant_name, date_of_service, total_amount, provider_name, policy_number |
| Medical bill | invoice_number, patient_name, date_of_service, total_amount, provider_name |

Both types also extract **line items** (service, code, amount) when present.

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/upload` | Upload and process a document |
| GET | `/api/upload/{id}/status` | Check processing status |
| GET | `/api/documents` | List all documents |
| GET | `/api/documents/{id}` | Document details with extraction |
| GET | `/api/review/queue` | Documents pending review |
| POST | `/api/review/{id}/approve` | Approve an extraction |
| POST | `/api/review/{id}/reject` | Reject an extraction |

## Confidence and review routing

- Document-level confidence is a weighted average: 80% field scores + 20% line item scores.
- A document goes to review if:
  - confidence < 0.8, or
  - any critical field is missing (e.g. claim_number, date_of_service, total_amount).
- The Streamlit Review Queue tab shows per-field confidence with color coding and approve/reject actions.

## Tests

```bash
pytest -v
```

Runs schema validation, confidence scoring, API smoke tests, and end-to-end extraction flow.
