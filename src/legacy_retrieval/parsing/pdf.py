from io import BytesIO

import pdfplumber


def parse_pdf_bytes(data: bytes) -> str:
    """Extract text from PDF bytes, preserving page markers."""
    pages: list[str] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {i}]\n{text}")
    return "\n\n".join(pages)


def parse_pdf_file(path: str) -> str:
    with open(path, "rb") as f:
        return parse_pdf_bytes(f.read())
