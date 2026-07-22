from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from pathlib import Path
import shutil

from ogma.json_store import read_json, write_json
from ogma.repository import JsonRepository, SqliteRepository
from ogma.sqlite_store import SqliteStore


@dataclass(frozen=True)
class ArchiveStorage:
    data_dir: Path
    shared_folders: list[str]
    campaign_folders: list[str]
    backend: str = "sqlite"

    @property
    def shared_data_dir(self) -> Path:
        return self.data_dir / "shared"

    @property
    def campaigns_dir(self) -> Path:
        return self.data_dir / "campaigns"

    @property
    def settings_path(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def clipboard_cache_dir(self) -> Path:
        return self.data_dir / ".cache" / "clipboard"

    @property
    def sqlite_db_path(self) -> Path:
        return self.data_dir / "ogma.db"

    @cached_property
    def sqlite(self) -> SqliteStore:
        return SqliteStore(self.sqlite_db_path)

    @cached_property
    def repository(self):
        if self.backend == "sqlite":
            return SqliteRepository(self.sqlite_db_path)
        return JsonRepository(self.data_dir)

    def load(self, entity: str, scope: str = "shared", campaign_slug: str = "") -> list[dict]:
        return self.repository.load(entity, scope=scope, campaign_slug=campaign_slug)

    def save(self, entity: str, payload: list[dict], scope: str = "shared", campaign_slug: str = "") -> None:
        self.repository.save(entity, payload, scope=scope, campaign_slug=campaign_slug)

    def list(self, entity: str, scope: str = "shared", campaign_slug: str = "") -> list[dict]:
        return self.repository.list(entity, scope=scope, campaign_slug=campaign_slug)

    def _repository_sqlite_store(self) -> SqliteStore:
        repository_store = getattr(self.repository, "store", None)
        return repository_store if isinstance(repository_store, SqliteStore) else self.sqlite

    def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        campaign_slug: str = "",
        limit: int = 100,
    ) -> list[dict]:
        return self.repository.search(query, entity_types=entity_types, campaign_slug=campaign_slug, limit=limit)

    def ensure(self) -> None:
        for folder in self.shared_folders:
            (self.shared_data_dir / folder).mkdir(parents=True, exist_ok=True)
        self.campaigns_dir.mkdir(parents=True, exist_ok=True)

    def campaign_metadata_path(self, slug: str) -> Path:
        return self.campaigns_dir / slug / "campaign.json"

    def campaign_cover_directory(self, slug: str) -> Path:
        return self.campaigns_dir / slug / "cover"

    def maps_directory(self, scope: str, campaign_slug: str = "") -> Path:
        if scope == "campaign":
            return self.campaigns_dir / campaign_slug / "maps"
        return self.shared_data_dir / "maps"

    def world_maps_directory(self, campaign_slug: str) -> Path:
        return self.campaigns_dir / campaign_slug / "world-maps"

    def scenes_directory(self) -> Path:
        return self.shared_data_dir / "scenes"

    def audio_directory(self) -> Path:
        return self.shared_data_dir / "audio"

    def resources_directory(self) -> Path:
        return self.shared_data_dir / "resources"

    def characters_directory(self, campaign_slug: str) -> Path:
        return self.campaigns_dir / campaign_slug / "characters"

    def notes_directory(self, campaign_slug: str) -> Path:
        return self.campaigns_dir / campaign_slug / "notes"

    def gods_directory(self, campaign_slug: str) -> Path:
        return self.campaigns_dir / campaign_slug / "gods"

    def rules_directory(self) -> Path:
        return self.shared_data_dir / "rules"

    def maps_metadata_path(self, scope: str, campaign_slug: str = "") -> Path:
        return self.maps_directory(scope, campaign_slug) / "maps.json"

    def world_maps_metadata_path(self, campaign_slug: str) -> Path:
        return self.world_maps_directory(campaign_slug) / "world-maps.json"

    def scenes_metadata_path(self) -> Path:
        return self.scenes_directory() / "scenes.json"

    def audio_metadata_path(self) -> Path:
        return self.audio_directory() / "audio.json"

    def resources_metadata_path(self) -> Path:
        return self.resources_directory() / "resources.json"

    def characters_metadata_path(self, campaign_slug: str) -> Path:
        return self.characters_directory(campaign_slug) / "characters.json"

    def notes_metadata_path(self, campaign_slug: str) -> Path:
        return self.notes_directory(campaign_slug) / "notes.json"

    def gods_metadata_path(self, campaign_slug: str) -> Path:
        return self.gods_directory(campaign_slug) / "gods.json"

    def rules_metadata_path(self) -> Path:
        return self.rules_directory() / "rules.json"

    def maps_tags_path(self, scope: str, campaign_slug: str = "") -> Path:
        return self.maps_directory(scope, campaign_slug) / "tags.json"

    def scenes_tags_path(self) -> Path:
        return self.scenes_directory() / "tags.json"

    def audio_tags_path(self) -> Path:
        return self.audio_directory() / "tags.json"

    def audio_categories_path(self) -> Path:
        return self.audio_directory() / "categories.json"

    def resources_tags_path(self) -> Path:
        return self.resources_directory() / "tags.json"

    def resources_categories_path(self) -> Path:
        return self.resources_directory() / "categories.json"

    def characters_groups_path(self, campaign_slug: str) -> Path:
        return self.characters_directory(campaign_slug) / "groups.json"

    def characters_tags_path(self, campaign_slug: str) -> Path:
        return self.characters_directory(campaign_slug) / "tags.json"

    def notes_tags_path(self, campaign_slug: str) -> Path:
        return self.notes_directory(campaign_slug) / "tags.json"

    def gods_domains_path(self, campaign_slug: str) -> Path:
        return self.gods_directory(campaign_slug) / "domains.json"

    def gods_alignments_path(self, campaign_slug: str) -> Path:
        return self.gods_directory(campaign_slug) / "alignments.json"

    def rules_tags_path(self) -> Path:
        return self.rules_directory() / "tags.json"

    def rules_sources_path(self) -> Path:
        return self.rules_directory() / "sources.json"

    def load_campaigns(self) -> list[dict]:
        if self.backend == "sqlite":
            return self.sqlite.load_metadata_list("campaigns", scope="shared", fallback=[])
        campaigns = []
        for path in sorted(self.campaigns_dir.glob("*/campaign.json")):
            metadata = read_json(path, fallback={})
            if isinstance(metadata, dict):
                metadata["slug"] = path.parent.name
                metadata.setdefault("foundry_slug", path.parent.name)
                campaigns.append(metadata)
        return sorted(campaigns, key=lambda item: item.get("created_at", ""), reverse=True)

    def save_campaigns(self, campaigns: list[dict]) -> None:
        if self.backend == "sqlite":
            self.sqlite.save_metadata_list("campaigns", campaigns, scope="shared")
            return
        for campaign in campaigns:
            slug = str(campaign.get("slug", "")).strip()
            if not slug:
                continue
            payload = campaign.copy()
            payload.pop("slug", None)
            write_json(self.campaign_metadata_path(slug), payload)

    def save_campaign(self, campaign: dict) -> None:
        if self.backend == "sqlite":
            self.sqlite.save_entity_item("campaigns", campaign, scope="shared")
            return
        self.save_campaigns([campaign])

    def load_labels(
        self,
        label_type: str,
        default_labels: list[str],
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> list[str]:
        if self.backend == "sqlite":
            labels = self.sqlite.load_label_list(label_type, scope=scope, campaign_slug=campaign_slug, fallback=[])
            return labels or default_labels[:]
        return default_labels[:]

    def save_labels(
        self,
        label_type: str,
        labels: list[str],
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> None:
        if self.backend == "sqlite":
            self.sqlite.save_label_list(label_type, labels, scope=scope, campaign_slug=campaign_slug)

    def migrate_json_content_if_needed(self) -> None:
        if self.sqlite.get_meta("content_migrated") == "1":
            self.sqlite.clear_legacy_payload_tables()
            return
        content_paths = self._metadata_json_paths()
        existing_content_paths = [path for path in content_paths if path.exists()]
        if not existing_content_paths and self.sqlite.has_content():
            self.sqlite.set_meta("content_migrated", "1")
            return

        backup_dir = self.data_dir.parent / "backups" / f"sqlite-migration-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        imported = self._import_json_content()
        self.sqlite.clear_legacy_payload_tables()
        self.sqlite.set_meta("content_migrated", "1")
        self.sqlite.set_meta("content_migration_counts", imported)
        if existing_content_paths:
            for path in existing_content_paths:
                relative = path.relative_to(self.data_dir)
                target = backup_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                try:
                    path.unlink()
                except OSError:
                    pass

    def _import_json_content(self) -> str:
        counts: dict[str, int] = {}
        campaigns = self.load_campaigns_json()
        self.sqlite.save_metadata_list("campaigns", campaigns, scope="shared")
        counts["campaigns"] = len(campaigns)
        shared_entities = {
            "maps": self.maps_metadata_path("shared"),
            "scenes": self.scenes_metadata_path(),
            "audio": self.audio_metadata_path(),
            "resources": self.resources_metadata_path(),
            "rules": self.rules_metadata_path(),
        }
        for entity, path in shared_entities.items():
            items = read_json(path, fallback=[])
            items = items if isinstance(items, list) else []
            self.sqlite.save_metadata_list(entity, items, scope="shared")
            counts[entity] = len(items)
        for campaign in campaigns:
            slug = str(campaign.get("slug", "")).strip()
            if not slug:
                continue
            for entity, path in {
                "world_maps": self.world_maps_metadata_path(slug),
                "maps": self.maps_metadata_path("campaign", slug),
                "characters": self.characters_metadata_path(slug),
                "notes": self.notes_metadata_path(slug),
                "gods": self.gods_metadata_path(slug),
            }.items():
                items = read_json(path, fallback=[])
                items = items if isinstance(items, list) else []
                self.sqlite.save_metadata_list(entity, items, scope="campaign", campaign_slug=slug)
                counts[f"{entity}:{slug}"] = len(items)
        self._import_json_labels(campaigns)
        return ",".join(f"{key}={value}" for key, value in sorted(counts.items()))

    def load_campaigns_json(self) -> list[dict]:
        campaigns = []
        for path in sorted(self.campaigns_dir.glob("*/campaign.json")):
            metadata = read_json(path, fallback={})
            if isinstance(metadata, dict):
                slug = path.parent.name
                metadata["slug"] = slug
                metadata.setdefault("foundry_slug", slug)
                campaigns.append(metadata)
        return sorted(campaigns, key=lambda item: item.get("created_at", ""), reverse=True)

    def _import_json_labels(self, campaigns: list[dict]) -> None:
        label_paths = {
            ("rules:tags", "shared", ""): self.rules_tags_path(),
            ("rules:sources", "shared", ""): self.rules_sources_path(),
            ("maps:tags", "shared", ""): self.maps_tags_path("shared"),
            ("scenes:tags", "shared", ""): self.scenes_tags_path(),
            ("audio:tags", "shared", ""): self.audio_tags_path(),
            ("audio:categories", "shared", ""): self.audio_categories_path(),
            ("resources:tags", "shared", ""): self.resources_tags_path(),
            ("resources:categories", "shared", ""): self.resources_categories_path(),
        }
        for campaign in campaigns:
            slug = str(campaign.get("slug", "")).strip()
            if not slug:
                continue
            label_paths[("maps:tags", "campaign", slug)] = self.maps_tags_path("campaign", slug)
            label_paths[("characters:tags", "campaign", slug)] = self.characters_tags_path(slug)
            label_paths[("characters:groups", "campaign", slug)] = self.characters_groups_path(slug)
            label_paths[("notes:tags", "campaign", slug)] = self.notes_tags_path(slug)
            label_paths[("gods:domains", "campaign", slug)] = self.gods_domains_path(slug)
            label_paths[("gods:alignments", "campaign", slug)] = self.gods_alignments_path(slug)
        for (label_type, scope, campaign_slug), path in label_paths.items():
            labels = read_json(path, fallback=[])
            if isinstance(labels, list):
                self.sqlite.save_label_list(label_type, [str(item) for item in labels], scope=scope, campaign_slug=campaign_slug)

    def _metadata_json_paths(self) -> list[Path]:
        paths = [
            self.rules_metadata_path(), self.rules_tags_path(), self.rules_sources_path(),
            self.maps_metadata_path("shared"), self.maps_tags_path("shared"),
            self.scenes_metadata_path(), self.scenes_tags_path(),
            self.audio_metadata_path(), self.audio_tags_path(), self.audio_categories_path(),
            self.resources_metadata_path(), self.resources_tags_path(), self.resources_categories_path(),
        ]
        for campaign_dir in sorted(self.campaigns_dir.glob("*")):
            if not campaign_dir.is_dir():
                continue
            slug = campaign_dir.name
            paths.extend([
                self.campaign_metadata_path(slug),
                self.world_maps_metadata_path(slug),
                self.maps_metadata_path("campaign", slug),
                self.maps_tags_path("campaign", slug),
                self.characters_metadata_path(slug),
                self.characters_tags_path(slug),
                self.characters_groups_path(slug),
                self.notes_metadata_path(slug),
                self.notes_tags_path(slug),
                self.gods_metadata_path(slug),
                self.gods_domains_path(slug),
                self.gods_alignments_path(slug),
            ])
        return paths

    def load_maps(self, scope: str, campaign_slug: str = "") -> list[dict]:
        return self.load("maps", scope=scope, campaign_slug=campaign_slug)

    def save_maps(self, scope: str, maps: list[dict], campaign_slug: str = "") -> None:
        self.save("maps", maps, scope=scope, campaign_slug=campaign_slug)

    def load_scenes(self) -> list[dict]:
        return self.load("scenes", scope="shared")

    def save_scenes(self, scenes: list[dict]) -> None:
        self.save("scenes", scenes, scope="shared")

    def load_audio_tracks(self) -> list[dict]:
        return self.load("audio", scope="shared")

    def save_audio_tracks(self, tracks: list[dict]) -> None:
        self.save("audio", tracks, scope="shared")

    def load_resources(self) -> list[dict]:
        return self.load("resources", scope="shared")

    def save_resources(self, resources: list[dict]) -> None:
        self.save("resources", resources, scope="shared")

    def load_generators(self) -> list[dict]:
        if self.backend == "sqlite":
            return self.sqlite.load_metadata_list("generators", scope="shared", fallback=[])
        return []

    def load_generator(self, generator_id: str) -> dict | None:
        if self.backend == "sqlite":
            return self.sqlite.load_generator(generator_id)
        return None

    def save_generators(self, generators: list[dict]) -> None:
        if self.backend == "sqlite":
            self.sqlite.save_metadata_list("generators", generators, scope="shared")

    def load_rules(self) -> list[dict] | None:
        if self.backend == "sqlite":
            rules = self.load("rules", scope="shared")
            return rules if isinstance(rules, list) else None
        rules = read_json(self.rules_metadata_path(), fallback=None)
        return rules if isinstance(rules, list) else None

    def save_rules(self, rules: list[dict]) -> None:
        self.save("rules", rules, scope="shared")

    def save_rule_item(self, rule: dict) -> None:
        if self.backend == "sqlite":
            self._repository_sqlite_store().save_entity_item("rules", rule, scope="shared")
            return
        rules = self.load_rules() or []
        rule_id = str(rule.get("id", "")).strip()
        for index, existing in enumerate(rules):
            if str(existing.get("id", "")).strip() == rule_id:
                rules[index] = rule
                break
        else:
            rules.append(rule)
        self.save_rules(rules)

    def delete_rule_item(self, rule_id: str) -> bool:
        if self.backend == "sqlite":
            return self._repository_sqlite_store().delete_entity_item("rules", rule_id, scope="shared")
        rules = self.load_rules() or []
        kept_rules = [rule for rule in rules if str(rule.get("id", "")).strip() != str(rule_id or "").strip()]
        if len(kept_rules) == len(rules):
            return False
        self.save_rules(kept_rules)
        return True

    def replace_rule_field_value(
        self,
        field: str,
        old_value: str,
        new_value: str,
        updated_at: str,
    ) -> list[str]:
        if self.backend == "sqlite":
            return self._repository_sqlite_store().replace_rule_field_value(field, old_value, new_value, updated_at)
        rules = self.load_rules() or []
        old_key = str(old_value or "").strip().casefold()
        moved_rule_ids: list[str] = []
        for rule in rules:
            if str(rule.get(field, "") or "").strip().casefold() != old_key:
                continue
            rule[field] = new_value
            rule["updated_at"] = updated_at
            moved_rule_ids.append(str(rule.get("id", "")))
        if moved_rule_ids:
            self.save_rules(rules)
        return moved_rule_ids

    def load_characters(self, campaign_slug: str) -> list[dict]:
        return self.load("characters", scope="campaign", campaign_slug=campaign_slug)

    def save_characters(self, campaign_slug: str, characters: list[dict]) -> None:
        self.save("characters", characters, scope="campaign", campaign_slug=campaign_slug)

    def load_notes(self, campaign_slug: str) -> list[dict]:
        if self.backend == "sqlite":
            notes = self.load("notes", scope="campaign", campaign_slug=campaign_slug)
            return notes if isinstance(notes, list) else []
        notes = read_json(self.notes_metadata_path(campaign_slug), fallback=[])
        return notes if isinstance(notes, list) else []

    def save_notes(self, campaign_slug: str, notes: list[dict]) -> None:
        self.save("notes", notes, scope="campaign", campaign_slug=campaign_slug)

    def load_gods(self, campaign_slug: str) -> list[dict]:
        if self.backend == "sqlite":
            gods = self.load("gods", scope="campaign", campaign_slug=campaign_slug)
            return gods if isinstance(gods, list) else []
        gods = read_json(self.gods_metadata_path(campaign_slug), fallback=[])
        return gods if isinstance(gods, list) else []

    def save_gods(self, campaign_slug: str, gods: list[dict]) -> None:
        self.save("gods", gods, scope="campaign", campaign_slug=campaign_slug)
