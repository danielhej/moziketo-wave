#!/usr/bin/env python3
"""Import wave catalog from WP export JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.import_catalog import import_catalog_payload


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import WP JSON export into wave catalog")
    parser.add_argument("json_path", type=Path, help="Path to export JSON (array or object)")
    args = parser.parse_args()
    payload = json.loads(args.json_path.read_text(encoding="utf-8"))
    async with SessionLocal() as session:
        result = await import_catalog_payload(session, payload)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
