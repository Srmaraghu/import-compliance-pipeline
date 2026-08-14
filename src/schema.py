"""
Basic schema definitions for extraction pipeline.
"""
from typing import Optional
from pydantic import BaseModel


class ExtractionResult(BaseModel):
    """Basic extraction result from a single source."""
    source: str
    fields: list
    raw_notes: Optional[str] = None
