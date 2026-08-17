"""
Utility functions for fetching and processing PDFs.

Text extraction uses markitdown which preserves table structure as markdown,
giving the LLM much cleaner input than raw pdfplumber text. Page images are
still rasterized as a fallback for the vision model when table columns are
ambiguous in text alone.
"""
import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pymupdf as fitz
import requests
from markitdown import MarkItDown

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DatasheetContent:
    """Container for extracted PDF content."""
    source_url: str
    local_path: Path
    text_by_page: List[str]
    page_images_b64: List[str]
    fetched_live: bool


def fetch_pdf(url: str, timeout: int = 30) -> Path:
    """Download PDF to local cache."""
    local_name = url.split("/")[-1] or "datasheet.pdf"
    local_path = CACHE_DIR / local_name
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    local_path.write_bytes(resp.content)
    logger.info(f"Downloaded PDF to {local_path}")
    return local_path


def extract_markdown(pdf_path: Path) -> str:
    """Extract PDF content as markdown using markitdown.
    
    Preserves table structure much better than plain text extraction —
    tables come out as markdown with pipes and headers intact, so the
    LLM can read column values without guessing the layout.
    """
    md = MarkItDown()
    result = md.convert(str(pdf_path))
    text = result.text_content or ""
    logger.info(f"markitdown extracted {len(text)} chars from {pdf_path.name}")
    return text


def rasterize_pages_b64(pdf_path: Path, dpi: int = 150) -> List[str]:
    """Render PDF pages to base64-encoded JPEG for vision models."""
    images_b64 = []
    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("jpeg")
        images_b64.append(base64.b64encode(img_bytes).decode("utf-8"))
        logger.debug(f"Rasterized page {i+1} to JPEG")
    doc.close()
    return images_b64


def fetch_datasheet(url: str, offline_fixture: Path = None) -> DatasheetContent:
    """
    Fetch manufacturer datasheet PDF with fallback to offline fixture.
    Text is extracted via markitdown (preserves table structure as markdown).
    Page images are also rasterized for vision-based cross-checking.
    """
    fetched_live = True
    try:
        local_path = fetch_pdf(url)
    except Exception as exc:
        logger.warning(f"Live fetch of {url} failed: {exc}")
        if offline_fixture and offline_fixture.exists():
            logger.warning(f"Falling back to offline fixture: {offline_fixture}")
            local_path = offline_fixture
            fetched_live = False
        else:
            raise

    # markitdown gives us the whole doc as one markdown string
    markdown_text = extract_markdown(local_path)
    images = rasterize_pages_b64(local_path)

    return DatasheetContent(
        source_url=url,
        local_path=local_path,
        text_by_page=[markdown_text],  # single entry — markitdown doesn't split by page
        page_images_b64=images,
        fetched_live=fetched_live,
    )


def read_text_file(path: Path) -> str:
    """Read a text file."""
    return path.read_text(encoding="utf-8")
