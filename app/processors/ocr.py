from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from app.schemas import OCRPage, OCRResult, OCRWord, SourceBBox

if TYPE_CHECKING:
    from PIL import Image as ImageModule


def _ocr_image(image: ImageModule.Image, page_number: int) -> OCRPage:
    import pytesseract

    text = pytesseract.image_to_string(image) or ""
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    words: list[OCRWord] = []
    for idx in range(len(data.get("text", []))):
        raw_text = (data["text"][idx] or "").strip()
        if not raw_text:
            continue
        confidence = float(data["conf"][idx]) if data["conf"][idx] not in ("-1", -1) else 0.0
        bbox = SourceBBox(
            x=float(data["left"][idx]),
            y=float(data["top"][idx]),
            width=float(data["width"][idx]),
            height=float(data["height"][idx]),
        )
        words.append(
            OCRWord(
                text=raw_text,
                confidence=max(min(confidence / 100.0, 1.0), 0.0),
                bbox=bbox,
                page_number=page_number,
            )
        )

    return OCRPage(page_number=page_number, text=text, words=words)


def run_ocr(file_path: str) -> OCRResult:
    from PIL import Image

    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in {".png", ".jpg", ".jpeg"}:
        with Image.open(path) as img:
            page = _ocr_image(img.convert("RGB"), page_number=1)
            return OCRResult(full_text=page.text, pages=[page])

    if suffix == ".pdf":
        import fitz

        pages: list[OCRPage] = []
        with fitz.open(path) as pdf_doc:
            for index, pdf_page in enumerate(pdf_doc, start=1):
                pix = pdf_page.get_pixmap(dpi=220)
                image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                pages.append(_ocr_image(image, page_number=index))

        return OCRResult(
            full_text="\n".join(p.text for p in pages if p.text),
            pages=pages,
        )

    raise ValueError(f"Unsupported file extension for OCR: {suffix}")
