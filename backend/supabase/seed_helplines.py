"""Seed the editable helpline directory in Supabase.

Run from the backend directory with:
    python supabase/seed_helplines.py
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from supabase import Client, create_client

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "backend" / "data" / "helplines.json"


class HelplineSeed(BaseModel):
    """Validated representation of one helpline seed row."""

    model_config = ConfigDict(extra="forbid")

    name: str
    number: str
    category: str
    description: str
    available_hours: str
    locale: str = "all"


def load_seed_rows(path: Path = DATA_PATH) -> list[HelplineSeed]:
    """Load and validate helpline rows from the checked-in JSON file."""

    with path.open("r", encoding="utf-8") as handle:
        raw_rows: Any = json.load(handle)
    if not isinstance(raw_rows, list):
        raise ValueError("Helpline seed data must be a JSON array")
    return [HelplineSeed.model_validate(row) for row in raw_rows]


def get_client() -> Client:
    """Create a Supabase client from environment variables."""

    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(url, key)


def seed_helplines(client: Client, rows: list[HelplineSeed]) -> int:
    """Upsert validated rows and return the number of rows sent."""

    payload = [row.model_dump() for row in rows]
    if not payload:
        return 0
    client.table("helplines").upsert(payload, on_conflict="name,number").execute()
    return len(payload)


def main() -> None:
    """Load the local seed and insert it into Supabase."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rows = load_seed_rows()
    inserted = seed_helplines(get_client(), rows)
    LOGGER.info("Upserted %d helpline rows", inserted)


if __name__ == "__main__":
    main()
