from __future__ import annotations

import json

import requests
import streamlit as st

CONFIDENCE_THRESHOLD = 0.8

st.set_page_config(page_title="Document Intake", layout="wide")
st.title("Document Intake System")

backend_url = st.sidebar.text_input("Backend URL", value="http://127.0.0.1:8000").rstrip("/")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get(path: str, timeout: int = 15) -> dict | list | None:
    try:
        resp = requests.get(f"{backend_url}{path}", timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"GET {path} failed ({resp.status_code}): {resp.text}")
    except requests.RequestException as exc:
        st.warning(f"Backend not reachable: {exc}")
    return None


def api_post(path: str, **kwargs) -> dict | None:
    try:
        resp = requests.post(f"{backend_url}{path}", timeout=300, **kwargs)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"POST {path} failed ({resp.status_code}): {resp.text}")
    except requests.RequestException as exc:
        st.warning(f"Backend not reachable: {exc}")
    return None


def render_field(name: str, field: dict) -> None:
    conf = field.get("confidence", 0)
    color = "red" if conf < CONFIDENCE_THRESHOLD else "green"
    st.markdown(
        f"**{name}**: {field.get('value')}  \n"
        f":{color}[confidence: {conf}]"
    )
    evidences = field.get("evidence") or []
    if evidences and evidences[0]:
        ev = evidences[0]
        if ev.get("quote"):
            st.caption(f"quote: {ev['quote']}")


def render_extraction(extraction: dict) -> None:
    fields = extraction.get("fields", {})
    if not fields:
        st.info("No extracted fields.")
        return

    for name, field in fields.items():
        render_field(name, field)
    st.divider()

    line_items = extraction.get("line_items", [])
    if line_items:
        st.subheader("Line Items")
        for row in line_items:
            conf = row.get("confidence", 0)
            color = "red" if conf < CONFIDENCE_THRESHOLD else "green"
            cols = st.columns([3, 2, 2, 2])
            cols[0].write(row.get("service") or "-")
            cols[1].write(row.get("code") or "-")
            cols[2].write(f"${row.get('amount', 0):.2f}" if row.get("amount") is not None else "-")
            cols[3].markdown(f":{color}[{conf}]")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

upload_tab, review_tab, documents_tab = st.tabs(["Upload", "Review Queue", "Documents"])

# ---- Upload tab -----------------------------------------------------------

with upload_tab:
    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "png", "jpg", "jpeg"])
    if st.button("Upload and Process", type="primary", disabled=uploaded_file is None):
        if uploaded_file is None:
            st.warning("Please select a file.")
        else:
            files = {
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    uploaded_file.type or "application/octet-stream",
                )
            }
            result = api_post("/api/upload", files=files)
            if result:
                st.success("Upload complete.")
                st.json(result)
                detail = api_get(f"/api/documents/{result['document_id']}")
                if detail and detail.get("extraction"):
                    st.subheader("Extraction Detail")
                    render_extraction(detail["extraction"])

# ---- Review Queue tab -----------------------------------------------------

with review_tab:
    if st.button("Refresh Queue"):
        pass

    queue = api_get("/api/review/queue")
    if queue is None:
        st.stop()

    if not queue:
        st.info("No documents waiting for review.")
    else:
        for item in queue:
            doc_id = item.get("document_id") or item.get("id")
            with st.expander(
                f"{item['original_filename']} | "
                f"{item.get('document_type', '?')} | "
                f"confidence: {item.get('confidence_score', '?')}"
            ):
                st.caption(f"Document ID: {doc_id}")

                detail = api_get(f"/api/documents/{doc_id}")
                if detail and detail.get("extraction"):
                    render_extraction(detail["extraction"])

                    col_approve, col_reject = st.columns(2)
                    if col_approve.button("Approve", key=f"approve_{doc_id}", type="primary"):
                        resp = api_post(f"/api/review/{doc_id}/approve", data={"extraction_json": ""})
                        if resp:
                            st.success(f"Approved {doc_id[:8]}")
                            st.rerun()
                    if col_reject.button("Reject", key=f"reject_{doc_id}"):
                        resp = api_post(f"/api/review/{doc_id}/reject")
                        if resp:
                            st.warning(f"Rejected {doc_id[:8]}")
                            st.rerun()

# ---- Documents tab --------------------------------------------------------

with documents_tab:
    if st.button("Refresh Documents"):
        pass

    docs = api_get("/api/documents")
    if docs is None:
        st.stop()

    if not docs:
        st.info("No documents yet.")
    else:
        for doc in docs[:20]:
            with st.expander(
                f"{doc['original_filename']} | {doc['status']} | "
                f"confidence: {doc.get('confidence_score', '?')}"
            ):
                st.caption(f"ID: {doc['id']}")
                detail = api_get(f"/api/documents/{doc['id']}")
                if detail and detail.get("extraction"):
                    render_extraction(detail["extraction"])
                elif detail:
                    st.code(json.dumps(detail, indent=2), language="json")
