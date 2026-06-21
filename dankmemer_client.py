import logging
from typing import Any, Dict, Optional
from dankmemer import DankMemerClient
import json as _json
import re as _re
from pathlib import Path as _Path

logger = logging.getLogger(__name__)


def _parse_skill_categories(items: list) -> dict:
    """Parse raw skill items from data.json into {category: [{base, name, max_tier}]}."""
    cats: dict[str, list[dict]] = {}
    for s in items:
        m = _re.match(r"^(.+)-(\d+)$", s["id"])
        if not m:
            continue
        base, tier = m.group(1), int(m.group(2))
        cat = s["extra"]["category"]
        clean_name = _re.sub(r"\s+(IX|VIII|VII|VI|V|IV|III|II|I)$", "", s["name"])
        if cat not in cats:
            cats[cat] = []
        existing = next((x for x in cats[cat] if x["base"] == base), None)
        if existing:
            existing["max_tier"] = max(existing["max_tier"], tier)
        else:
            cats[cat].append({"base": base, "name": clean_name, "max_tier": tier})
    return cats


class DankMemerGameClient:
    def __init__(self, cache_ttl_hours: int = 1, retry_attempts: int = 3, retry_backoff: float = 1.0):
        self._cache_ttl_hours = cache_ttl_hours
        self._retry_attempts = retry_attempts
        self._retry_backoff = retry_backoff
        self._client: Optional[DankMemerClient] = None
        self.fish_by_id: Dict[str, Any] = {}
        self.fish_by_name: Dict[str, Any] = {}
        self.location_by_id: Dict[str, Any] = {}
        self.location_by_name: Dict[str, Any] = {}
        self.tool_by_id: Dict[str, Any] = {}
        self.tool_by_name: Dict[str, Any] = {}
        self.bait_by_id: Dict[str, Any] = {}
        self.bait_by_name: Dict[str, Any] = {}
        self.npc_by_id: Dict[str, Any] = {}
        self.npc_by_name: Dict[str, Any] = {}
        self.event_by_id: Dict[str, Any] = {}
        self.event_by_name: Dict[str, Any] = {}
        self.skill_categories: Dict[str, list] = {}
        self.location_creature_map: Dict[str, list] = {}

    async def connect(self) -> None:
        if self._client is not None:
            return
        self._client = DankMemerClient(
            cache_ttl_hours=self._cache_ttl_hours,
            retry_attempts=self._retry_attempts,
            retry_backoff=self._retry_backoff,
        )
        await self._client.__aenter__()

    async def __aenter__(self) -> "DankMemerGameClient":
        await self.connect()
        await self.preload()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def preload(self) -> None:
        await self.connect()
        logger.info("Preloading DankMemer game data...")
        try:
            logger.info("Loading creatures...")
            logger.debug("Calling creatures.query()")
            creatures = await self._client.creatures.query()
            logger.debug("creatures.query() returned %d items", len(creatures))
            for item in creatures:
                self.fish_by_id[item.id] = item
                self.fish_by_name[item.name.lower()] = item
        except Exception:
            logger.warning("Failed to preload creatures", exc_info=True)

        try:
            logger.info("Loading locations...")
            logger.debug("Calling locations.query()")
            locations = await self._client.locations.query()
            logger.debug("locations.query() returned %d items", len(locations))
            for loc in locations:
                self.location_by_id[loc.id] = loc
                self.location_by_name[loc.name.lower()] = loc
        except Exception:
            logger.warning("Failed to preload locations", exc_info=True)

        try:
            logger.info("Loading tools...")
            logger.debug("Calling tools.query()")
            tools = await self._client.tools.query()
            logger.debug("tools.query() returned %d items", len(tools))
            for tool in tools:
                self.tool_by_id[tool.id] = tool
                self.tool_by_name[tool.name.lower()] = tool
        except Exception:
            logger.warning("Failed to preload tools", exc_info=True)

        try:
            logger.info("Loading baits...")
            logger.debug("Calling baits.query()")
            baits = await self._client.baits.query()
            logger.debug("baits.query() returned %d items", len(baits))
            for bait in baits:
                self.bait_by_id[bait.id] = bait
                self.bait_by_name[bait.name.lower()] = bait
        except Exception:
            logger.warning("Failed to preload baits", exc_info=True)

        try:
            logger.info("Loading npcs...")
            logger.debug("Calling npcs.query()")
            npcs = await self._client.npcs.query()
            logger.debug("npcs.query() returned %d items", len(npcs))
            for npc in npcs:
                self.npc_by_id[npc.id] = npc
                self.npc_by_name[npc.name.lower()] = npc
        except Exception:
            logger.warning("Failed to preload npcs", exc_info=True)

        try:
            logger.info("Loading events...")
            logger.debug("Calling events.query()")
            events = await self._client.events.query()
            logger.debug("events.query() returned %d items", len(events))
            for event in events:
                self.event_by_id[event.id] = event
                self.event_by_name[event.name.lower()] = event
        except Exception:
            logger.warning("Failed to preload events", exc_info=True)

        # Build cross-reference: location → resolved Creature objects
        for loc_id, loc in self.location_by_id.items():
            creature_ids = loc.extra.get("creatures") or [] if hasattr(loc.extra, "get") else []
            self.location_creature_map[loc_id] = [
                self.fish_by_id[cid]
                for cid in creature_ids
                if cid in self.fish_by_id
            ]
        logger.debug("Built location_creature_map for %d locations", len(self.location_creature_map))

        try:
            data_path = _Path(__file__).parent / "data.json"
            raw_skills = _json.loads(data_path.read_text(encoding="utf-8"))["data"]["skills"]["items"]
            self.skill_categories = _parse_skill_categories(raw_skills)
            logger.info("Loaded %d skill categories", len(self.skill_categories))
        except Exception:
            logger.warning("Failed to load skill categories from data.json", exc_info=True)

        logger.info(
            "Preload complete: %d fish, %d locations, %d tools, %d baits, %d npcs, %d events",
            len(self.fish_by_id),
            len(self.location_by_id),
            len(self.tool_by_id),
            len(self.bait_by_id),
            len(self.npc_by_id),
            len(self.event_by_id),
        )

    def get_fish(self, query: str):
        if query in self.fish_by_id:
            return self.fish_by_id[query]
        return self.fish_by_name.get(query.lower())

    def get_location(self, query: str):
        if query in self.location_by_id:
            return self.location_by_id[query]
        return self.location_by_name.get(query.lower())

    def get_tool(self, query: str):
        if query in self.tool_by_id:
            return self.tool_by_id[query]
        return self.tool_by_name.get(query.lower())

    def get_bait(self, query: str):
        if query in self.bait_by_id:
            return self.bait_by_id[query]
        return self.bait_by_name.get(query.lower())

    def get_npc(self, query: str):
        if query in self.npc_by_id:
            return self.npc_by_id[query]
        return self.npc_by_name.get(query.lower())

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                logger.warning("Error closing DankMemerClient", exc_info=True)
            finally:
                self._client = None
