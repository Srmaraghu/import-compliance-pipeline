"""
Utility functions for fetching and processing PDFs.
"""
import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pymupdf as fitz
import pdfplumber
import requests

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


def extract_text_per_page(pdf_path: Path) -> List[str]:
    """Extract text from each page of PDF using pdfplumber."""
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append(text)
            logger.debug(f"Extracted {len(text)} chars from page {i+1}")
    return pages


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
    Returns text and base64 images for vision-based extraction.
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
    
    text_pages = extract_text_per_page(local_path)
    images = rasterize_pages_b64(local_path)
    
    logger.info(
        f"Datasheet processed: {len(text_pages)} pages, "
        f"{sum(len(t) for t in text_pages)} total chars"
    )
    
    return DatasheetContent(
        source_url=url,
        local_path=local_path,
        text_by_page=text_pages,
        page_images_b64=images,
        fetched_live=fetched_live,
    )


def read_text_file(path: Path) -> str:
    """Read a text file."""
    return path.read_text(encoding="utf-8")
