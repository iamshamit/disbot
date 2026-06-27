"""One-time script: upload all fish/location/tool/bait images as application emojis.

Usage:
    python scripts/upload_app_emojis.py

Requires DISCORD_BOT_TOKEN in .env. Reads data.json, uploads any emoji not
already uploaded, and writes data/app_emojis.json with the {item_id: ...} mapping.
Re-running is safe — already-uploaded names are skipped.
"""
from __future__ import annotations
import asyncio
import base64
import json
import re
import sys
from pathlib import Path

import aiohttp
from dotenv import load_dotenv
import os

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
if not TOKEN:
    sys.exit("DISCORD_BOT_TOKEN not set in .env")

API = "https://discord.com/api/v10"
HEADERS = {"Authorization": f"Bot {TOKEN}"}
OUT_PATH = ROOT / "data" / "app_emojis.json"


def sanitize(item_id: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]", "_", item_id)
    name = re.sub(r"_+", "_", name).strip("_")
    return (name or "item")[:32]


async def get_app_id(session: aiohttp.ClientSession) -> str:
    async with session.get(f"{API}/users/@me", headers=HEADERS) as r:
        r.raise_for_status()
        data = await r.json()
        return data["id"]


async def list_existing(session: aiohttp.ClientSession, app_id: str) -> dict[str, dict]:
    async with session.get(f"{API}/applications/{app_id}/emojis", headers=HEADERS) as r:
        r.raise_for_status()
        data = await r.json()
        return {e["name"]: e for e in data.get("items", [])}


async def upload_one(
    session: aiohttp.ClientSession, app_id: str, name: str, url: str, animated: bool
) -> dict | None:
    async with session.get(url) as r:
        if r.status != 200:
            print(f"  [warn] could not download {url}")
            return None
        img = await r.read()

    mime = "image/gif" if animated else "image/png"
    b64 = base64.b64encode(img).decode()
    payload = {"name": name, "image": f"data:{mime};base64,{b64}"}

    while True:
        async with session.post(
            f"{API}/applications/{app_id}/emojis",
            headers={**HEADERS, "Content-Type": "application/json"},
            json=payload,
        ) as r:
            if r.status == 429:
                body = await r.json()
                wait = body.get("retry_after", 1.0)
                print(f"  [rate limit] waiting {wait:.1f}s…")
                await asyncio.sleep(wait)
                continue
            if r.status not in (200, 201):
                body = await r.text()
                print(f"  [error {r.status}] {name}: {body[:120]}")
                return None
            return await r.json()


async def main() -> None:
    with open(ROOT / "data.json", encoding="utf-8") as f:
        raw = json.load(f)["data"]

    items: list[dict] = []
    for cat in ("creatures", "locations", "tools", "baits"):
        for item in raw[cat]["items"]:
            url = item.get("imageURL", "")
            if url:
                items.append({
                    "id": item["id"],
                    "name": sanitize(item["id"]),
                    "url": url,
                    "animated": url.endswith(".gif"),
                })

    print(f"Items to upload: {len(items)}")

    async with aiohttp.ClientSession() as session:
        app_id = await get_app_id(session)
        print(f"Application ID: {app_id}")

        existing = await list_existing(session, app_id)
        print(f"Already uploaded: {len(existing)}")

        # Load existing mapping if any
        mapping: dict[str, dict] = {}
        if OUT_PATH.exists():
            with open(OUT_PATH, encoding="utf-8") as f:
                mapping = json.load(f)

        # Seed mapping from existing emojis (in case JSON was lost)
        for item in items:
            if item["name"] in existing:
                e = existing[item["name"]]
                mapping[item["id"]] = {
                    "emoji_id": int(e["id"]),
                    "name": e["name"],
                    "animated": e.get("animated", False),
                }

        to_upload = [i for i in items if i["name"] not in existing]
        print(f"To upload: {len(to_upload)}")

        for idx, item in enumerate(to_upload, 1):
            print(f"  [{idx}/{len(to_upload)}] {item['name']}…", end=" ", flush=True)
            result = await upload_one(session, app_id, item["name"], item["url"], item["animated"])
            if result and "id" in result:
                mapping[item["id"]] = {
                    "emoji_id": int(result["id"]),
                    "name": result["name"],
                    "animated": result.get("animated", False),
                }
                print(f"ok (id={result['id']})")
            else:
                print("skipped")
            # Stay well under Discord's rate limit
            await asyncio.sleep(0.5)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)
    print(f"\nSaved {len(mapping)} entries → {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
