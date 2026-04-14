#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from webcam_seed_common import load_seed_file, validate_entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Eagle Eye approved webcam seed data.")
    parser.add_argument("seed_file", help="Path to approved_webcams_seed.json or approved_webcams_seed.yaml")
    args = parser.parse_args()

    try:
        _, entries = load_seed_file(args.seed_file)
    except Exception as exc:
        print(f"[seed] failed to load '{args.seed_file}': {exc}", file=sys.stderr)
        return 2

    errors = validate_entries(entries)
    if errors:
        print(f"[seed] validation failed with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"[seed] validation passed for {len(entries)} webcam record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
