"""
Pipeline - adds extraction from buyer form using Gemini.
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


def load_sources():
    """Load the three source documents."""
    buyer_form = tools.read_text_file(DATA_DIR / "buyer_form.txt")
    call_notes = tools.read_text_file(DATA_DIR / "call_notes.txt")
    return {"buyer_form": buyer_form, "call_notes": call_notes}


def extract_buyer_form(buyer_form_text: str) -> dict:
    """Use Gemini to extract structured data from buyer form."""
    client = GeminiClient()
    print("Extracting buyer form data with Gemini...")
    result = client.generate_json(BUYER_FORM_PROMPT, buyer_form_text)
    return result


def run():
    """Run the pipeline."""
    sources = load_sources()
    print(f"Loaded buyer form ({len(sources['buyer_form'])} chars)")
    print(f"Loaded call notes ({len(sources['call_notes'])} chars)")

    buyer_form_data = extract_buyer_form(sources["buyer_form"])
    print("\nExtracted from buyer form:")
    print(json.dumps(buyer_form_data, indent=2))

    return buyer_form_data
