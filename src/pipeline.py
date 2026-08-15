"""
Basic pipeline to load and structure source documents.
"""
from pathlib import Path
from . import tools

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def load_sources():
    """Load the three source documents."""
    print("Loading source documents...")
    
    buyer_form = tools.read_text_file(DATA_DIR / "buyer_form.txt")
    call_notes = tools.read_text_file(DATA_DIR / "call_notes.txt")
    
    print(f"Loaded buyer form ({len(buyer_form)} chars)")
    print(f"Loaded call notes ({len(call_notes)} chars)")
    
    return {
        "buyer_form": buyer_form,
        "call_notes": call_notes,
    }


def run():
    """Run the basic pipeline."""
    sources = load_sources()
    
    return sources
