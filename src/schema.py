"""
Structured data contracts for the import compliance pipeline.

Every fact that ends up in the human-readable draft has to be traceable to one of
the three sources (datasheet / buyer form / call notes), or explicitly marked as
not present in any source ("pending from manufacturer"). These models exist so
that traceability is enforced in code, not just in prose.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SourceName(str, Enum):
    DATASHEET = "datasheet"
    BUYER_FORM = "buyer_form"
    CALL_NOTES = "call_notes"


class Confidence(str, Enum):
    HIGH = "high"      # explicitly stated in a written document
    MEDIUM = "medium"  # stated but verbal / secondhand / a guess, per the source itself
    LOW = "low"        # inferred or ambiguous
    NONE = "none"      # not available anywhere -> pending from manufacturer


class SourcedValue(BaseModel):
    """A single value as reported by a single source."""
    source: SourceName
    value: str
    confidence: Confidence
    verbatim_or_paraphrase_note: Optional[str] = Field(
        default=None,
        description="Short note on how the value was reported, e.g. 'stated verbally, no written record'.",
    )


class Field_(BaseModel):
    """
    One checklist fact (e.g. 'rated output power'), potentially reported
    differently -- or not at all -- across the three sources.
    """
    field_name: str
    checklist_category: str  # product_identity | manufacturer_identity | test_evidence | labeling | importer_paperwork
    values: List[SourcedValue] = Field(default_factory=list)
    conflict: bool = False
    conflict_note: Optional[str] = None
    resolved_status: str = Field(
        description=(
            "One of: 'established' (written, uncontested), "
            "'reported_verbally' (call notes only, unverified), "
            "'disputed' (sources disagree), "
            "'pending' (no source has it)."
        )
    )


class ExtractionResult(BaseModel):
    """Raw per-source extraction, before reconciliation."""
    source: SourceName
    fields: List[Field_]
    raw_notes: Optional[str] = None


class ReconciledRecord(BaseModel):
    """Final cross-source reconciliation, one entry per checklist fact."""
    fields: List[Field_]
    open_questions_for_factory: List[str]
    pending_items: List[str]
    disagreements: List[str]
