from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ogma.json_store import read_json, write_json
from ogma.sqlite_store import SqliteStore


class ArchiveRepository(ABC):
    @abstractmethod
    def load(self, entity: str, scope: str = "shared", campaign_slug: str = "") -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def save(self, entity: str, payload: list[dict], scope: str = "shared", campaign_slug: str = "") -> None:
        raise NotImplementedError

    @abstractmethod
    def list(self, entity: str, scope: str = "shared", campaign_slug: str = "") -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        campaign_slug: str = "",
        limit: int = 100,
    ) -> list[dict]:
        raise NotImplementedError


class JsonRepository(ArchiveRepository):
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _metadata_path(self, entity: str, scope: str, campaign_slug: str) -> Path:
        if entity == "maps":
            if scope == "campaign":
                return self.data_dir / "campaigns" / campaign_slug / "maps" / "maps.json"
            return self.data_dir / "shared" / "maps" / "maps.json"
        if entity == "world_maps":
            return self.data_dir / "campaigns" / campaign_slug / "world-maps" / "world-maps.json"
        if entity == "scenes":
            return self.data_dir / "shared" / "scenes" / "scenes.json"
        if entity == "audio":
            return self.data_dir / "shared" / "audio" / "audio.json"
        if entity == "resources":
            return self.data_dir / "shared" / "resources" / "resources.json"
        if entity == "rules":
            return self.data_dir / "shared" / "rules" / "rules.json"
        if entity == "characters":
            return self.data_dir / "campaigns" / campaign_slug / "characters" / "characters.json"
        if entity == "notes":
            return self.data_dir / "campaigns" / campaign_slug / "notes" / "notes.json"
        if entity == "gods":
            return self.data_dir / "campaigns" / campaign_slug / "gods" / "gods.json"
        raise ValueError(f"Unsupported entity for JsonRepository: {entity}")

    def load(self, entity: str, scope: str = "shared", campaign_slug: str = "") -> list[dict]:
        return read_json(self._metadata_path(entity, scope, campaign_slug), fallback=[])

    def save(self, entity: str, payload: list[dict], scope: str = "shared", campaign_slug: str = "") -> None:
        path = self._metadata_path(entity, scope, campaign_slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, payload)

    def list(self, entity: str, scope: str = "shared", campaign_slug: str = "") -> list[dict]:
        return self.load(entity, scope, campaign_slug)

    def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        campaign_slug: str = "",
        limit: int = 100,
    ) -> list[dict]:
        needle = (query or "").strip().casefold()
        if not needle:
            return []
        entity_types = entity_types or ["maps", "scenes", "audio", "resources", "rules", "characters", "notes", "gods"]
        results = []
        for entity in entity_types:
            if entity == "campaigns":
                for path in sorted((self.data_dir / "campaigns").glob("*/campaign.json")):
                    item = read_json(path, fallback={})
                    if not isinstance(item, dict):
                        continue
                    item["slug"] = path.parent.name
                    haystack = " ".join(str(item.get(key, "")) for key in ("name", "description", "system", "slug"))
                    if needle in haystack.casefold():
                        results.append({"entity_type": entity, "item_id": item.get("slug", ""), "campaign_slug": item.get("slug", ""), "payload": item})
                        if len(results) >= limit:
                            return results
                continue
            if entity in {"characters", "notes", "gods"} and not campaign_slug:
                continue
            scope = "campaign" if entity in {"maps", "characters", "notes", "gods"} and campaign_slug else "shared"
            items = self.load(entity, scope=scope, campaign_slug=campaign_slug)
            for item in items:
                haystack = " ".join(
                    [
                        *(str(item.get(key, "")) for key in ("title", "name", "description", "content", "source", "alignment", "pantheon", "symbol")),
                        " ".join(str(tag) for tag in item.get("domains", []) if tag),
                    ]
                )
                if needle in haystack.casefold():
                    results.append({"entity_type": entity, "item_id": item.get("id", ""), "payload": item})
                    if len(results) >= limit:
                        return results
        return results


class SqliteRepository(ArchiveRepository):
    def __init__(self, db_path: Path) -> None:
        self.store = SqliteStore(db_path)

    def load(self, entity: str, scope: str = "shared", campaign_slug: str = "") -> list[dict]:
        return self.store.load_metadata_list(entity, scope=scope, campaign_slug=campaign_slug, fallback=[])

    def save(self, entity: str, payload: list[dict], scope: str = "shared", campaign_slug: str = "") -> None:
        self.store.save_metadata_list(entity, payload, scope=scope, campaign_slug=campaign_slug)

    def list(self, entity: str, scope: str = "shared", campaign_slug: str = "") -> list[dict]:
        return self.load(entity, scope=scope, campaign_slug=campaign_slug)

    def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        campaign_slug: str = "",
        limit: int = 100,
    ) -> list[dict]:
        return self.store.search_spotlight(
            query=query,
            entity_types=entity_types or [],
            campaign_slug=campaign_slug,
            limit=limit,
        )
