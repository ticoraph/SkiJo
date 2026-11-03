#!/usr/bin/env python3
"""Download source slope maps for optional local extraction experiments."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = PROJECT_ROOT / "data" / "imported" / "slope_map_inventory.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "maps"
USER_AGENT = "SkiJo resort-slope-maps research downloader/1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accept-source-terms",
        action="store_true",
        help="Confirm that you reviewed and accept each source site's terms.",
    )
    parser.add_argument("--limit", type=int, help="Maximum number of maps to download.")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between requests (default: 1.0).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Local ignored directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    return parser.parse_args()


def download_map(session: requests.Session, row: pd.Series, output_dir: Path) -> str:
    source_url = row.get("source_url")
    if not isinstance(source_url, str) or not source_url.strip():
        return "no_source_url"

    destination = output_dir / str(row["asset_name"])
    if destination.exists():
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if digest == row["sha256"]:
            return "cached"

    response = session.get(source_url, timeout=90)
    response.raise_for_status()
    payload = response.content
    digest = hashlib.sha256(payload).hexdigest()
    if digest != row["sha256"]:
        return "hash_mismatch"

    temporary_path = destination.with_suffix(destination.suffix + ".tmp")
    temporary_path.write_bytes(payload)
    temporary_path.replace(destination)
    return "downloaded"


def main() -> None:
    args = parse_args()
    if not args.accept_source_terms:
        print(
            "Pass --accept-source-terms after reviewing the source websites' terms and licences.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    inventory = pd.read_csv(INVENTORY_PATH)
    if args.limit is not None:
        inventory = inventory.head(args.limit)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        for position, (_, row) in enumerate(inventory.iterrows(), 1):
            try:
                status = download_map(session, row, output_dir)
            except requests.RequestException as error:
                status = f"http_error:{type(error).__name__}"
            counts[status] = counts.get(status, 0) + 1
            print(f"[{position}/{len(inventory)}] {row['owner_slug']}: {status}")
            if position < len(inventory) and status == "downloaded":
                time.sleep(max(args.delay, 0))

    print("Download summary:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
