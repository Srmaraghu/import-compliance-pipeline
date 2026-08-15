"""
Pipeline wired as a LangGraph StateGraph.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from . import prompts, tools
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


class PipelineState(TypedDict, total=False):
    datasheet_text: str
    datasheet_images_b64: List[str]
    datasheet_fetched_live: bool
    buyer_form_text: str
    call_notes_text: str
    extraction_datasheet: Dict[str, Any]
    extraction_buyer_form: Dict[str, Any]
    extraction_call_notes: Dict[str, Any]
    reconciled: Dict[str, Any]
    draft_markdown: str

# Helper funcitons

def _client() -> GeminiClient:
    return GeminiClient()


def _call_json(system: str, user_content) -> Dict[str, Any]:
    return _client().generate_json(system, user_content)


def _call_text(system: str, user_content: str) -> str:
    return _client().generate_text(system, user_content)


#  Nodes

def fetch_datasheet_node(state: PipelineState) -> PipelineState:
    # downloads the PDF, extracts text per page, rasterizes pages to JPEG for vision
    content = tools.fetch_datasheet(DATASHEET_URL, offline_fixture=OFFLINE_FIXTURE)
    combined_text = "\n\n----- PAGE BREAK -----\n\n".join(content.text_by_page)
    logger.info(
        "Datasheet fetched (%s). %d page(s), %d chars.",
        "live" if content.fetched_live else "OFFLINE FIXTURE",
        len(content.text_by_page),
        len(combined_text),
    )
    return {
        "datasheet_text": combined_text,
        "datasheet_images_b64": content.page_images_b64,
        "datasheet_fetched_live": content.fetched_live,
    }


def load_manual_sources_node(state: PipelineState) -> PipelineState:
    # reads buyer_form.txt and call_notes.txt from disk into state
    return {
        "buyer_form_text": tools.read_text_file(DATA_DIR / "buyer_form.txt"),
        "call_notes_text": tools.read_text_file(DATA_DIR / "call_notes.txt"),
    }


def extract_datasheet_node(state: PipelineState) -> PipelineState:
    # sends text layer + page images to Gemini vision; extracts structured fields
    content_blocks = ["Extracted text from PDF:\n\n" + state["datasheet_text"]]
    for i, img_b64 in enumerate(state["datasheet_images_b64"]):
        content_blocks.append(f"\n\nPage {i + 1} image:")
        content_blocks.append({"inline_data": {"mime_type": "image/jpeg", "data": img_b64}})
    result = _call_json(prompts.DATASHEET_EXTRACTION_SYSTEM, content_blocks)
    time.sleep(4)
    return {"extraction_datasheet": result}


def extract_buyer_form_node(state: PipelineState) -> PipelineState:
    # extracts structured fields from the plain-text buyer intake form
    result = _call_json(prompts.BUYER_FORM_EXTRACTION_SYSTEM, state["buyer_form_text"])
    time.sleep(4)
    return {"extraction_buyer_form": result}


def extract_call_notes_node(state: PipelineState) -> PipelineState:
    # extracts fields from informal call notes; all values treated as low confidence
    result = _call_json(prompts.CALL_NOTES_EXTRACTION_SYSTEM, state["call_notes_text"])
    time.sleep(4)
    return {"extraction_call_notes": result}


def reconcile_node(state: PipelineState) -> PipelineState:
    # merges all three extractions; flags conflicts, verbal-only values, and pending items
    payload = {
        "datasheet_extraction": state["extraction_datasheet"],
        "buyer_form_extraction": state["extraction_buyer_form"],
        "call_notes_extraction": state["extraction_call_notes"],
    }
    user_content = "Reconcile the following three extractions:\n\n" + json.dumps(payload, indent=2)
    result = _call_json(prompts.RECONCILIATION_SYSTEM, user_content)
    time.sleep(4)
    return {"reconciled": result}


def draft_node(state: PipelineState) -> PipelineState:
    # turns the reconciled record into the human-readable Markdown compliance draft
    fetch_note = (
        "The datasheet was fetched LIVE from the manufacturer URL for this run."
        if state["datasheet_fetched_live"]
        else "NOTE: live fetch failed; an offline cached copy was used instead."
    )
    user_content = (
        f"Reconciled record:\n\n{json.dumps(state['reconciled'], indent=2)}\n\n"
        f"Fetch status: {fetch_note}"
    )
    markdown = _call_text(prompts.DRAFT_SYSTEM, user_content)
    time.sleep(4)
    return {"draft_markdown": markdown}


def save_outputs_node(state: PipelineState) -> PipelineState:
    # writes structured_output.json and draft.md to /output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    structured = {
        "datasheet_source_url": DATASHEET_URL,
        "datasheet_fetched_live": state["datasheet_fetched_live"],
        "extractions": {
            "datasheet": state["extraction_datasheet"],
            "buyer_form": state["extraction_buyer_form"],
            "call_notes": state["extraction_call_notes"],
        },
        "reconciled": state["reconciled"],
    }
    (OUTPUT_DIR / "structured_output.json").write_text(
        json.dumps(structured, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "draft.md").write_text(state["draft_markdown"], encoding="utf-8")
    logger.info("Wrote output/structured_output.json and output/draft.md")
    return {}


# assembly of the graph 

def build_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("fetch_datasheet", fetch_datasheet_node)
    graph.add_node("load_manual_sources", load_manual_sources_node)
    graph.add_node("extract_datasheet", extract_datasheet_node)
    graph.add_node("extract_buyer_form", extract_buyer_form_node)
    graph.add_node("extract_call_notes", extract_call_notes_node)
    graph.add_node("reconcile", reconcile_node)
    graph.add_node("draft", draft_node)
    graph.add_node("save_outputs", save_outputs_node)

    graph.set_entry_point("fetch_datasheet")
    graph.add_edge("fetch_datasheet", "load_manual_sources")
    graph.add_edge("load_manual_sources", "extract_datasheet")
    graph.add_edge("extract_datasheet", "extract_buyer_form")
    graph.add_edge("extract_buyer_form", "extract_call_notes")
    graph.add_edge("extract_call_notes", "reconcile")
    graph.add_edge("reconcile", "draft")
    graph.add_edge("draft", "save_outputs")
    graph.add_edge("save_outputs", END)

    return graph.compile()


def run() -> PipelineState:
    app = build_graph()
    final_state = app.invoke({})
    return final_state
