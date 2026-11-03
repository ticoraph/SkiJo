#!/usr/bin/env python3
"""Execute the public resort-slope-maps notebook without paid API calls."""

from __future__ import annotations

import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "slope_map_extraction.ipynb"


def main() -> None:
    os.chdir(PROJECT_ROOT)
    print(f"Executing {NOTEBOOK_PATH.relative_to(PROJECT_ROOT)}...")
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    NotebookClient(
        notebook,
        timeout=900,
        kernel_name="python3",
        allow_errors=False,
    ).execute()
    print("Analysis complete. Results are available in data/outputs/.")


if __name__ == "__main__":
    main()
