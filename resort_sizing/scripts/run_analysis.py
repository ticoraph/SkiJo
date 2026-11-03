#!/usr/bin/env python3
"""Execute the resort-sizing notebooks in their required order."""

from __future__ import annotations

import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = (
    PROJECT_ROOT / "notebooks" / "resort_size_classification.ipynb",
    PROJECT_ROOT / "notebooks" / "resort_size_prediction.ipynb",
)


def main() -> None:
    os.chdir(PROJECT_ROOT)

    for notebook_path in NOTEBOOKS:
        print(f"Executing {notebook_path.relative_to(PROJECT_ROOT)}...")
        notebook = nbformat.read(notebook_path, as_version=4)
        NotebookClient(
            notebook,
            timeout=600,
            kernel_name="python3",
            allow_errors=False,
        ).execute()

    print("Analysis complete. Results are available in data/outputs/.")


if __name__ == "__main__":
    main()
