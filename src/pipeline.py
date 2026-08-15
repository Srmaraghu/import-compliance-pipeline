"""
Pipeline - extracts from buyer form, call notes, and PDF datasheet using Gemini vision.
"""
import json
from pathlib import Path
from dotenv import load_dotenv
from . import tools
from .gemini_client import GeminiClient

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

BUYER_FORM_PROMPT = """You are extracting structured data from a buyer intake form.
Return ONLY a valid JSON object with these fields:
{
  "model_number": string or null,
  "rated_power": string or null,
  "manufacturer": string or null,
  "destination": string or null,
  "need_by_date": string or null
}
No markdown fences, no commentary, just JSON."""

CALL_NOTES_PROMPT = """You are extracting structured data from informal phone call notes.
These are verbal, unverified notes - treat them as low confidence.
Return ONLY a valid JSON object with these fields:
{
  "model_number": string or null,
  "rated_power": string or null,
  "ip_rating": string or null,
  "weight_kg": string or null,
  "test_body_mentioned": string or null,
  "efficiency_mentioned": string or null,
  "label_available": string or null
}
No markdown fences, no commentary, just JSON."""

DATASHEET_PROMPT = """You are extracting technical specifications from a manufacturer's PDF datasheet.
The PDF contains both extracted text and page images. Use BOTH to accurately read specification tables.

Extract the following fields for the SPECIFIC model mentioned in the context:
{
  "model_number": string or null,
  "rated_power": string or null,
  "ip_rating": string or null,
  "weight_kg": string or null,
  "max_efficiency": string or null,
  "test_certifications": string or null,
  "label_info": string or null
}
Return ONLY valid JSON, no markdown fences."""

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
    return client.generate_json(BUYER_FORM_PROMPT, buyer_form_text)


def extract_call_notes(call_notes_text: str) -> dict:
    """Use Gemini to extract structured data from call notes."""
    client = GeminiClient()
    print("Extracting call notes data...")
    return client.generate_json(CALL_NOTES_PROMPT, call_notes_text)


def extract_datasheet() -> dict:
    """Fetch and extract data from PDF datasheet using vision."""
    client = GeminiClient()
    print(f"\nFetching datasheet from {DATASHEET_URL}...")
    
    # Fetch PDF with text and images
    content = tools.fetch_datasheet(DATASHEET_URL, offline_fixture=OFFLINE_FIXTURE)
    
    # Combine text from all pages
    combined_text = "\n\n----- PAGE BREAK -----\n\n".join(content.text_by_page)
    
    print(f"Extracted {len(content.text_by_page)} pages, {len(combined_text)} chars")
    print("Running vision extraction on PDF pages...")
    
    # Build content blocks for vision model
    content_blocks = [
        "Extracted text from PDF:\n\n" + combined_text
    ]
    
    # Add page images for vision analysis
    for i, img_b64 in enumerate(content.page_images_b64):
        content_blocks.append(f"\n\nPage {i + 1} image:")
        content_blocks.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": img_b64
            }
        })
    
    result = client.generate_json(DATASHEET_PROMPT, content_blocks)
    result["_fetched_live"] = content.fetched_live
    return result


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

    return {
        "buyer_form": buyer_form_data,
        "call_notes": call_notes_data,
        "datasheet": datasheet_data
    }
