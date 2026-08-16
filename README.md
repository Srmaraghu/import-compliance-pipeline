# Import Compliance Pipeline 

Given a manufacturer datasheet, a buyer form, and some rough call notes, build a pipeline that pulls out the relevant facts, checks if they agree across sources, and writes a compliance draft for the Bangladesh import agent.

Uses **Google Gemini** (free tier). Get an API key at https://aistudio.google.com/apikey

> **Note on rate limits:** The free tier has a low RPM limit. The client supports multiple keys with automatic rotation — you can add up to 3 keys as a comma-separated list in `.env` (`GEMINI_API_KEY=key1,key2,key3`). With 3 free keys the pipeline runs without hitting limits.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your GEMINI_API_KEY
python run.py
```

Output goes to `output/`:
- `structured_output.json` — all extracted fields with source and confidence info
- `draft.md` — the actual compliance document

## The three sources

| # | What | Format | Where it comes from |
|---|------|--------|---------------------|
| 1 | Deye inverter datasheet | PDF | fetched live from the manufacturer URL |
| 2 | Buyer intake form | plain text | `data/buyer_form.txt` |
| 3 | Ramesh's call notes (Oct 2024) | plain text | `data/call_notes.txt` |

## How the pipeline works

```
fetch_datasheet → load_manual_sources → extract_datasheet → extract_buyer_form → extract_call_notes
                                                                                         │
                                                                                         ▼
                                                                                     reconcile
                                                                                         │
                                                                                         ▼
                                                                                       draft
                                                                                         │
                                                                                         ▼
                                                                                    save_outputs
```

Built with LangGraph, each step is a node in a state graph. Here's what each one does:

1. **fetch_datasheet** — downloads the PDF, extracts text with pdfplumber, and converts pages to images for vision
2. **extract_datasheet / extract_buyer_form / extract_call_notes** — one Gemini call per source, extracts structured fields. Each node validates the response against a Pydantic schema before moving on — if validation fails, it retries with the error fed back into the prompt
3. **reconcile** — compares all three extractions and marks each field as `established`, `reported_verbally`, `disputed`, or `pending`
4. **draft** — turns the reconciled data into the Markdown compliance doc
5. **save_outputs** — writes both files to `output/`

## Structured output and confidence rules

Every fact in `structured_output.json` has a `source` and a `confidence` level:
- `high` — explicitly stated in a written document
- `medium` — stated verbally or secondhand
- `low` — hedged, guessed, or inferred

A key rule enforced in the prompts: **if a value is inferred rather than explicitly stated, confidence can never be `high`**. This prevents things like "Country: China" being marked high just because it appears at the end of an address.

## Why vision + text for the datasheet

The datasheet covers 8 inverter models in one table. When you extract the text layer, the columns get scrambled — you can't tell which value belongs to which model. Instead of hardcoding a fix, I send both the raw text and a JPEG of each page to Gemini and tell it to read the SUN-5K column specifically from the image. Works more reliably than text-only extraction.

If the live PDF fetch fails (no internet, etc.), it falls back to a cached copy at `data/offline_fixture/` and notes it in the output.

## Repo layout

```
.
├── run.py
├── requirements.txt
├── data/
│   ├── buyer_form.txt
│   ├── call_notes.txt
│   └── offline_fixture/
│       └── datasheet_fixture.pdf
├── src/
│   ├── tools.py           # PDF download, text extraction, image rendering
│   ├── prompts.py         # loads prompts from yaml files
│   ├── prompts/           # one yaml file per prompt
│   ├── schema.py          # Pydantic models for validation
│   └── pipeline.py        # LangGraph graph
└── output/                # generated at runtime
```

## Things I'd improve with more time

- Run the three extraction nodes in parallel (they're independent and LangGraph supports fan-out)
- Try local OCR (e.g. Tesseract) as a first pass before sending images to Gemini — the vision call is the most expensive step, and for a clean digital PDF cheaper text extraction might be enough
- Add an eval set to catch prompt output drift between runs — right now the reconciliation is non-deterministic and could drop pending items across runs
- Add a critic node that reads the draft back and flags any sentence not traceable to a source
