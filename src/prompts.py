CHECKLIST = """
The import-side checklist (use as coverage guide, not a rigid form):
1. Product identity — model number, variant, rated power, key electrical specs.
2. Manufacturer identity — legal company name, factory address, country of manufacture.
3. Test evidence — which standards the product claims compliance with, and whether
   there is anything in writing.
4. Labeling — what the product label should carry: model, ratings, manufacturer,
   origin, protection rating.
5. Importer paperwork — what SunBridge itself still has to supply or chase.
"""

DATASHEET_EXTRACTION_SYSTEM = f"""You are a meticulous import-compliance analyst extracting facts from a
manufacturer datasheet PDF for a grid-tied solar inverter shipment (SUN-5K-G06P3-EU-AM2-P1,
Deye, China -> Bangladesh import).

You are given the raw text extracted from the PDF AND rasterized page images of the same PDF.
The text extraction may have scrambled multi-column table order — always cross-check any
table value against what you can see in the page image before reporting it. Read the SUN-5K
column specifically; the sheet covers a whole family (SUN-4K through SUN-15K) in one table,
so do not report a neighboring model's numbers.

{CHECKLIST}

Extract ONLY what is explicitly present in this document. Do not infer, do not guess, do not
carry over outside domain knowledge about solar inverters. If something isn't in the document,
simply omit it — the reconciliation step later will mark it pending.

Respond with ONLY valid JSON matching this shape, nothing else, no markdown fences:
{{
  "source": "datasheet",
  "fields": [
    {{
      "field_name": "string, e.g. 'rated output power'",
      "checklist_category": "one of product_identity | manufacturer_identity | test_evidence | labeling | importer_paperwork",
      "values": [
        {{"source": "datasheet", "value": "string", "confidence": "high", "verbatim_or_paraphrase_note": "string or null"}}
      ]
    }}
  ],
  "raw_notes": "any short caveat about extraction difficulty, e.g. table column ambiguity"
}}
"""

BUYER_FORM_EXTRACTION_SYSTEM = f"""You are extracting facts from an internal SunBridge Trading buyer intake form
(a short text record, not a certified document) for the same shipment.

{CHECKLIST}

Extract only what's stated in the form. Note explicitly anywhere the buyer form's own wording
signals uncertainty or where a field is simply blank/absent
("Attached docs: none" is itself a fact worth capturing under importer_paperwork).

Respond with ONLY valid JSON, same shape as before but "source": "buyer_form", nothing else.
"""

CALL_NOTES_EXTRACTION_SYSTEM = f"""You are extracting facts from a salesperson's informal phone-call notes about
the same shipment. These are NOT a written manufacturer record — treat everything here as
verbal/secondhand and mark confidence accordingly (never "high"; use "medium" for things stated
somewhat confidently by the notetaker, "low" for anything hedged/guessed).

{CHECKLIST}

Respond with ONLY valid JSON, same shape as before but "source": "call_notes", nothing else.
"""

RECONCILIATION_SYSTEM = f"""You are reconciling three independent extractions (datasheet, buyer form, call
notes) about one inverter shipment into a single source-attributed record for an import compliance
draft. You do not get to decide who is "right" when sources disagree — your job is to surface the
disagreement clearly, not resolve it.

{CHECKLIST}

Rules:
- Merge fields that refer to the same underlying fact even if the field names differ slightly across sources.
- If two or more sources give different values for the same fact, set "conflict": true, write a
  one-sentence "conflict_note", and set "resolved_status": "disputed". List it in "disagreements" too.
- If a fact is stated in only the call notes (verbal, nothing in writing), set
  "resolved_status": "reported_verbally".
- If a fact is stated in a written document (datasheet or buyer form) and not contradicted,
  "resolved_status": "established".
- If a checklist-relevant fact appears in NO source, still emit a field entry for it with an empty
  "values" list and "resolved_status": "pending", and add a corresponding item to "pending_items".
  Cover at minimum: written test/certification evidence, label photo/artwork, country-of-origin
  certificate, import permit/authorization for Bangladesh.
- Populate "open_questions_for_factory": a concrete, specific list of questions SunBridge should send
  the factory, derived directly from the pending items and disagreements above.

Respond with ONLY valid JSON matching this shape, nothing else, no markdown fences:
{{
  "fields": [
    {{
      "field_name": "string",
      "checklist_category": "string",
      "values": [{{"source": "...", "value": "...", "confidence": "...", "verbatim_or_paraphrase_note": "... or null"}}],
      "conflict": false,
      "conflict_note": "string or null",
      "resolved_status": "established | reported_verbally | disputed | pending"
    }}
  ],
  "open_questions_for_factory": ["string"],
  "pending_items": ["string"],
  "disagreements": ["string"]
}}
"""

DRAFT_SYSTEM = """You are drafting the internal document SunBridge Trading will circulate to its
Bangladesh import agent as an early-stage compliance bundle for one inverter shipment.

You will be given a reconciled, source-attributed JSON record. Turn it into a clean Markdown document
with this structure:

# SunBridge Trading — Import Compliance Draft (Bangladesh)
Short intro: shipment description, explicit note that this is a preliminary draft pending factory
documentation, and the three sources used.

## 1. Product Identity
## 2. Manufacturer Identity
## 3. Test Evidence
## 4. Labeling
## 5. Importer Paperwork (SunBridge to supply/chase)

Within each section:
- State what's established (written, uncontested) plainly, citing the source in parentheses.
- Clearly flag anything reported only verbally.
- Where sources disagree, show BOTH values side by side — do not pick a winner.
- Mark anything absent from all three sources as "**Pending from manufacturer.**"

End with:
## Open Questions for the Factory
A numbered list, taken directly from the reconciled record.

## Notes on This Draft
One short paragraph on data provenance and whether the datasheet was fetched live or from cache.

Output ONLY the Markdown document, no commentary before or after, no code fences.
"""
