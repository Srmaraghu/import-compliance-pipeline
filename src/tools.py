"""
Utility functions for fetching and processing PDFs.
"""
import requests
from pathlib import Path


def fetch_datasheet(url: str, offline_fixture: Path = None):
    """
    Fetch PDF datasheet from URL.
    Falls back to offline fixture if fetch fails.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        if offline_fixture and offline_fixture.exists():
            print(f"Using offline fixture: {offline_fixture}")
            return offline_fixture.read_bytes()
        raise


def read_text_file(path: Path) -> str:
    """Read a text file."""
    return path.read_text(encoding="utf-8")
