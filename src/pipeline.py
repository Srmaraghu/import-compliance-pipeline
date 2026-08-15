"""
Pipeline - extracts from buyer form, call notes, and PDF datasheet using Gemini vision.
Reconciles all three sources and generates a Markdown compliance draft.
"""
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from . import tools, prompts
from .gemini_client import GeminiClient

load_dotenv()

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"

DATASHEET_URL = (
    "https://www.deyeinverter.com/deyeinverter/2023/10/07/"
    "datasheet_sun-4-12k-g06p3-eu-am2-p1_231007_en.pdf"
)
OFFLINE_FIXTURE = DATA_DIR / "offline_fixture" / "datasheet_fixture.pdf"


def load_sources():
    """Load the three source documents."""
    buyer_form = tools.read_text_file(DATA_DIR / "buyer_form.txt")
    call_notes = tools.read_text_file(DATA_DIR / "call_notes.txt")
    return {"buyer_form": buyer_form, "call_notes": call_notes}


def extract_buyer_form(buyer_form_text: str) -> dict:
    """Use Gemini to extract structured data from buyer form."""
    client = GeminiClient()
    print("Extracting buyer form data...")
    return client.generate_json(prompts.BUYER_FORM_EXTRACTION_SYSTEM, buyer_form_text)


def extract_call_notes(call_notes_text: str) -> dict:
    """Use Gemini to extract structured data from call notes."""
    client = GeminiClient()
    print("Extracting call notes data...")
    return client.generate_json(prompts.CALL_NOTES_EXTRACTION_SYSTEM, call_notes_text)


def extract_datasheet() -> dict:
    """Fetch and extract data from PDF datasheet using vision."""
    client = GeminiClient()
    print(f"\nFetching datasheet from {DATASHEET_URL}...")

    content = tools.fetch_datasheet(DATASHEET_URL, offline_fixture=OFFLINE_FIXTURE)
    combined_text = "\n\n----- PAGE BREAK -----\n\n".join(content.text_by_page)

    print(f"Extracted {len(content.text_by_page)} pages, {len(combined_text)} chars")
    print("Running vision extraction on PDF pages...")

    content_blocks = ["Extracted text from PDF:\n\n" + combined_text]
    for i, img_b64 in enumerate(content.page_images_b64):
        content_blocks.append(f"\n\nPage {i + 1} image:")
        content_blocks.append({
            "inline_data": {"mime_type": "image/jpeg", "data": img_b64}
        })

    result = client.generate_json(prompts.DATASHEET_EXTRACTION_SYSTEM, content_blocks)
    result["_fetched_live"] = content.fetched_live
    return result


def generate_draft(reconciled: dict, fetched_live: bool) -> str:
    """Turn the reconciled record into a human-readable Markdown compliance draft."""
    client = GeminiClient()
    print("\nGenerating compliance draft...")

    fetch_note = (
        "The datasheet was fetched LIVE from the manufacturer URL for this run."
        if fetched_live
        else "NOTE: live fetch of the manufacturer datasheet URL failed; an offline "
             "cached copy of the same file was used instead."
    )
    user_content = (
        f"Reconciled record:\n\n{json.dumps(reconciled, indent=2)}\n\n"
        f"Fetch status: {fetch_note}"
    )
    return client.generate_text(prompts.DRAFT_SYSTEM, user_content)


def reconcile(datasheet: dict, buyer_form: dict, call_notes: dict) -> dict:
    """Cross-reference all three extractions with Gemini and flag conflicts/pending items."""
    client = GeminiClient()
    print("\nReconciling extractions across all three sources...")

    payload = {
        "datasheet_extraction": datasheet,
        "buyer_form_extraction": buyer_form,
        "call_notes_extraction": call_notes,
    }
    user_content = "Reconcile the following three extractions:\n\n" + json.dumps(payload, indent=2)
    result = client.generate_json(prompts.RECONCILIATION_SYSTEM, user_content)
    return result


def save_outputs(state: dict) -> None:
    """Write structured_output.json and draft.md to the output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    structured = {
        "datasheet_source_url": DATASHEET_URL,
        "datasheet_fetched_live": state["datasheet"].get("_fetched_live", False),
        "extractions": {
            "datasheet": state["datasheet"],
            "buyer_form": state["buyer_form"],
            "call_notes": state["call_notes"],
        },
        "reconciled": state["reconciled"],
    }
    (OUTPUT_DIR / "structured_output.json").write_text(
        json.dumps(structured, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "draft.md").write_text(state["draft"], encoding="utf-8")
    logger.info("Wrote output/structured_output.json and output/draft.md")
    print("\nSaved: output/structured_output.json")
    print("Saved: output/draft.md")


def run():
    """Run the pipeline."""
    sources = load_sources()
    print(f"Loaded buyer form ({len(sources['buyer_form'])} chars)")
    print(f"Loaded call notes ({len(sources['call_notes'])} chars)")

    buyer_form_data = extract_buyer_form(sources["buyer_form"])
    print("\nExtracted from buyer form:")
    print(json.dumps(buyer_form_data, indent=2))

    call_notes_data = extract_call_notes(sources["call_notes"])
    print("\nExtracted from call notes:")
    print(json.dumps(call_notes_data, indent=2))

    datasheet_data = extract_datasheet()
    print("\nExtracted from datasheet:")
    print(json.dumps(datasheet_data, indent=2))

    reconciled = reconcile(datasheet_data, buyer_form_data, call_notes_data)
    print("\nReconciled record:")
    print(json.dumps(reconciled, indent=2))

    fetched_live = datasheet_data.get("_fetched_live", False)
    draft = generate_draft(reconciled, fetched_live)
    print("\n--- DRAFT PREVIEW (first 500 chars) ---")
    print(draft[:500])

    result = {
        "buyer_form": buyer_form_data,
        "call_notes": call_notes_data,
        "datasheet": datasheet_data,
        "reconciled": reconciled,
        "draft": draft,
    }
    save_outputs(result)
    return result
