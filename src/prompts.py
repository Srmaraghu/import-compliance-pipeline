from pathlib import Path
import yaml

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load(filename: str) -> dict:
    with open(_PROMPTS_DIR / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


# shared checklist injected into extraction prompts
_checklist = _load("checklist.yaml")["checklist"]

# build each prompt, injecting the checklist where needed
def _inject(text: str) -> str:
    return text.replace("{checklist}", _checklist)

DATASHEET_EXTRACTION_SYSTEM: str = _inject(_load("datasheet_extraction.yaml")["system"])
BUYER_FORM_EXTRACTION_SYSTEM: str = _inject(_load("buyer_form_extraction.yaml")["system"])
CALL_NOTES_EXTRACTION_SYSTEM: str = _inject(_load("call_notes_extraction.yaml")["system"])
RECONCILIATION_SYSTEM: str = _inject(_load("reconciliation.yaml")["system"])
DRAFT_SYSTEM: str = _load("draft.yaml")["system"]
