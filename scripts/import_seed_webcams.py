#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from webcam_seed_common import load_seed_file, validate_entries


UPSERT_SQL = """
INSERT INTO webcams (
  id,
  name,
  provider,
  provider_camera_id,
  country,
  region,
  city,
  lat,
  lon,
  geom,
  category,
  subcategory,
  watch_url,
  embed_url,
  preview_image_url,
  access_mode,
  embed_allowed,
  source_confidence,
  tags,
  priority,
  metadata,
  active,
  approved,
  updated_at
) VALUES (
  %(id)s,
  %(name)s,
  %(provider)s,
  %(provider_camera_id)s,
  %(country)s,
  %(region)s,
  %(city)s,
  %(lat)s,
  %(lon)s,
  ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
  %(category)s,
  %(subcategory)s,
  %(watch_url)s,
  %(embed_url)s,
  %(preview_image_url)s,
  %(access_mode)s,
  %(embed_allowed)s,
  %(source_confidence)s,
  %(tags)s,
  %(priority)s,
  %(metadata)s::jsonb,
  TRUE,
  TRUE,
  %(updated_at)s
)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  provider = EXCLUDED.provider,
  provider_camera_id = EXCLUDED.provider_camera_id,
  country = EXCLUDED.country,
  region = EXCLUDED.region,
  city = EXCLUDED.city,
  lat = EXCLUDED.lat,
  lon = EXCLUDED.lon,
  geom = EXCLUDED.geom,
  category = EXCLUDED.category,
  subcategory = EXCLUDED.subcategory,
  watch_url = EXCLUDED.watch_url,
  embed_url = EXCLUDED.embed_url,
  preview_image_url = EXCLUDED.preview_image_url,
  access_mode = EXCLUDED.access_mode,
  embed_allowed = EXCLUDED.embed_allowed,
  source_confidence = EXCLUDED.source_confidence,
  tags = EXCLUDED.tags,
  priority = EXCLUDED.priority,
  metadata = EXCLUDED.metadata,
  active = TRUE,
  approved = TRUE,
  updated_at = EXCLUDED.updated_at
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Eagle Eye approved webcam seed data.")
    parser.add_argument(
        "--file",
        default="data/webcams/approved_webcams_seed.json",
        help="Path to approved_webcams_seed.json or approved_webcams_seed.yaml",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection string. Defaults to DATABASE_URL.",
    )
    args = parser.parse_args()

    if not args.database_url:
        print("[seed] DATABASE_URL is required via --database-url or environment.", file=sys.stderr)
        return 2

    try:
        _, entries = load_seed_file(args.file)
    except Exception as exc:
        print(f"[seed] failed to load '{args.file}': {exc}", file=sys.stderr)
        return 2

    errors = validate_entries(entries)
    if errors:
        print(f"[seed] validation failed with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    try:
        import psycopg
    except ModuleNotFoundError:
        print("[seed] psycopg is not installed. Install project dependencies before importing.", file=sys.stderr)
        return 2

    imported = 0
    updated_at = datetime.now(timezone.utc)
    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            for entry in entries:
                payload = dict(entry)
                payload["metadata"] = json.dumps(entry["metadata"])
                payload["updated_at"] = updated_at

                existing_id = _lookup_existing_id(cursor, entry)
                if existing_id:
                    payload["id"] = existing_id

                cursor.execute(UPSERT_SQL, payload)
                imported += 1
        connection.commit()

    print(f"[seed] imported {imported} webcam record(s) into Eagle Eye.")
    return 0


def _lookup_existing_id(cursor, entry: dict[str, object]) -> str | None:
    if entry.get("provider_camera_id"):
        cursor.execute(
            """
            SELECT id
            FROM webcams
            WHERE provider = %s AND provider_camera_id = %s
            """,
            (entry["provider"], entry["provider_camera_id"]),
        )
        match = cursor.fetchone()
        if match:
            return str(match[0])

    cursor.execute(
        """
        SELECT id
        FROM webcams
        WHERE provider = %s AND watch_url = %s
        """,
        (entry["provider"], entry["watch_url"]),
    )
    match = cursor.fetchone()
    return str(match[0]) if match else None


if __name__ == "__main__":
    raise SystemExit(main())
