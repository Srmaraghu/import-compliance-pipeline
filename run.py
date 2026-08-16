#!/usr/bin/env python3
"""
Entrypoint: runs the full import compliance pipeline end to end.

Usage:
    python run.py

Requires GEMINI_API_KEY in the environment (or a .env file).
Writes output/structured_output.json and output/draft.md.
"""
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

from src.pipeline import run  # noqa: E402


def main() -> int:
    try:
        run()
    except Exception:
        logging.exception("Pipeline failed.")
        return 1

    print("\n--- Pipeline complete ---")
    print("Wrote: output/structured_output.json")
    print("Wrote: output/draft.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
