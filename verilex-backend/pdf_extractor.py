import os
import tempfile
import logging

import fitz  # PyMuPDF
import requests

logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT = 60  # seconds
_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB hard cap


def download_and_extract_pdf(pdf_url: str) -> dict:
    """Download a PDF from *pdf_url* and extract its text.

    Returns a dict with keys:
        full_text  — complete text with [PAGE N] markers
        pages      — list of {"page_number": int, "text": str}
        page_count — total number of pages
    """
    logger.info("Downloading PDF: %s", pdf_url)

    headers = {"User-Agent": "Verilex-AI/1.0 (+https://verilex.ai)"}

    try:
        resp = requests.get(
            pdf_url, headers=headers, timeout=_DOWNLOAD_TIMEOUT, stream=True
        )
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise ValueError(f"HTTP error downloading PDF ({exc.response.status_code}): {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"Network error downloading PDF: {exc}") from exc

    # Stream into a /tmp file to avoid large memory spikes
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, dir="/tmp"
        ) as tmp_file:
            tmp_path = tmp_file.name
            bytes_written = 0
            for chunk in resp.iter_content(chunk_size=65536):
                bytes_written += len(chunk)
                if bytes_written > _MAX_PDF_BYTES:
                    raise ValueError(
                        f"PDF exceeds maximum allowed size of {_MAX_PDF_BYTES // (1024*1024)} MB."
                    )
                tmp_file.write(chunk)

        logger.info("PDF saved to %s (%d bytes)", tmp_path, bytes_written)
        return _extract_text(tmp_path)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _extract_text(pdf_path: str) -> dict:
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise ValueError(f"Could not open PDF file: {exc}") from exc

    pages = []
    full_text_parts = []

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_number = page_index + 1
            text = page.get_text("text")  # plain text, preserves layout order

            pages.append({"page_number": page_number, "text": text})
            full_text_parts.append(f"[PAGE {page_number}]\n{text}")

    finally:
        doc.close()

    full_text = "\n\n".join(full_text_parts)
    logger.info("Extracted %d pages, %d total chars", len(pages), len(full_text))

    return {
        "full_text": full_text,
        "pages": pages,
        "page_count": len(pages),
    }
