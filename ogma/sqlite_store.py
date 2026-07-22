import json
import sqlite3
import re
import threading
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any


_WRITE_COORDINATOR = threading.RLock()


class DataIntegrityError(RuntimeError):
    """Stored metadata cannot be decoded without risking data loss."""


class SqliteStore:
    """Small SQLite helper for Oghma metadata collections."""

    ENTITY_TABLES = {
        "campaigns": "campaigns",
        "maps": "maps",
        "world_maps": "world_maps",
        "scenes": "scenes",
        "audio": "audio_tracks",
        "resources": "resources",
        "rules": "rules",
        "characters": "characters",
        "notes": "notes",
        "gods": "gods",
        "generators": "generators",
    }

    ENTITY_TABLE_COLUMNS = {
        "campaigns": [
            "slug", "name", "description", "system", "foundry_slug", "cover_image",
            "created_at", "updated_at", "json_payload", "position",
        ],
        "maps": [
            "id", "scope", "campaign_slug", "title", "filename", "original_filename",
            "file_path", "uploaded_at", "created_at", "updated_at", "json_payload", "position",
        ],
        "world_maps": [
            "id", "campaign_slug", "title", "base_map_id", "created_at", "updated_at", "json_payload", "position",
        ],
        "scenes": [
            "id", "title", "filename", "original_filename", "file_path", "uploaded_at",
            "created_at", "updated_at", "json_payload", "position",
        ],
        "audio": [
            "id", "title", "description", "source_type", "source", "file_path",
            "category", "uploaded_at", "created_at", "updated_at", "json_payload", "position",
        ],
        "resources": [
            "id", "title", "description", "source_type", "source", "file_path",
            "category", "created_at", "updated_at", "json_payload", "position",
        ],
        "rules": [
            "id", "title", "content", "source", "tag", "created_at", "updated_at",
            "json_payload", "position",
        ],
        "characters": [
            "id", "campaign_slug", "name", "race", "gender", "attitude", "appearance",
            "biography", "notes", "image", "created_at", "updated_at", "json_payload", "position",
        ],
        "notes": [
            "id", "campaign_slug", "title", "content", "session_no", "status",
            "note_type", "created_at", "updated_at", "json_payload", "position",
        ],
        "gods": [
            "id", "campaign_slug", "name", "alignment", "pantheon", "symbol",
            "source", "description", "created_at", "updated_at", "json_payload", "position",
        ],
        "generators": [
            "id", "title", "description", "dice_expression", "category",
            "created_at", "updated_at", "json_payload", "position",
        ],
    }

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @contextmanager
    def _transaction(self):
        with _WRITE_COORDINATOR:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                if connection.in_transaction:
                    connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            finally:
                connection.close()

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    system TEXT NOT NULL DEFAULT '',
                    foundry_slug TEXT NOT NULL DEFAULT '',
                    cover_image TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS maps (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL DEFAULT 'shared',
                    campaign_slug TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    filename TEXT NOT NULL DEFAULT '',
                    original_filename TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL DEFAULT '',
                    uploaded_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS world_maps (
                    id TEXT PRIMARY KEY,
                    campaign_slug TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    base_map_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(campaign_slug) REFERENCES campaigns(slug) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scenes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    filename TEXT NOT NULL DEFAULT '',
                    original_filename TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL DEFAULT '',
                    uploaded_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS audio_tracks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL DEFAULT '',
                    uploaded_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS characters (
                    id TEXT PRIMARY KEY,
                    campaign_slug TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    race TEXT NOT NULL DEFAULT '',
                    gender TEXT NOT NULL DEFAULT '',
                    attitude TEXT NOT NULL DEFAULT '',
                    appearance TEXT NOT NULL DEFAULT '',
                    biography TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    image TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(campaign_slug) REFERENCES campaigns(slug) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    campaign_slug TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    session_no INTEGER,
                    status TEXT NOT NULL DEFAULT '',
                    note_type TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(campaign_slug) REFERENCES campaigns(slug) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS gods (
                    id TEXT PRIMARY KEY,
                    campaign_slug TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    alignment TEXT NOT NULL DEFAULT '',
                    pantheon TEXT NOT NULL DEFAULT '',
                    symbol TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(campaign_slug) REFERENCES campaigns(slug) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS generators (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    dice_expression TEXT NOT NULL DEFAULT '1d20',
                    category TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS generator_rows (
                    id TEXT PRIMARY KEY,
                    generator_id TEXT NOT NULL,
                    range_min INTEGER NOT NULL,
                    range_max INTEGER NOT NULL,
                    result_markdown TEXT NOT NULL DEFAULT '',
                    position INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(generator_id) REFERENCES generators(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS item_tags (
                    entity_type TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    tag_id INTEGER NOT NULL,
                    campaign_slug TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (entity_type, item_id, tag_id),
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS item_categories (
                    entity_type TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    campaign_slug TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (entity_type, item_id, category_id),
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scoped_tag_lists (
                    entity_type TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'shared',
                    campaign_slug TEXT NOT NULL DEFAULT '',
                    tag_id INTEGER NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (entity_type, scope, campaign_slug, tag_id),
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scoped_category_lists (
                    entity_type TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'shared',
                    campaign_slug TEXT NOT NULL DEFAULT '',
                    category_id INTEGER NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (entity_type, scope, campaign_slug, category_id),
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS spotlight_search USING fts5(
                    item_id UNINDEXED,
                    entity_type UNINDEXED,
                    campaign_slug UNINDEXED,
                    title,
                    body,
                    tags,
                    tokenize='unicode61'
                );

                CREATE TABLE IF NOT EXISTS metadata_lists (
                    entity TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    campaign_slug TEXT NOT NULL DEFAULT '',
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (entity, scope, campaign_slug)
                );

                CREATE TABLE IF NOT EXISTS label_lists (
                    label_type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    campaign_slug TEXT NOT NULL DEFAULT '',
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (label_type, scope, campaign_slug)
                );

                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_metadata_lists_entity_scope
                    ON metadata_lists(entity, scope);
                CREATE INDEX IF NOT EXISTS idx_label_lists_type_scope
                    ON label_lists(label_type, scope);
                CREATE INDEX IF NOT EXISTS idx_campaigns_slug ON campaigns(slug);
                CREATE INDEX IF NOT EXISTS idx_maps_campaign_slug ON maps(campaign_slug);
                CREATE INDEX IF NOT EXISTS idx_maps_updated_at ON maps(updated_at);
                CREATE INDEX IF NOT EXISTS idx_world_maps_campaign_slug ON world_maps(campaign_slug);
                CREATE INDEX IF NOT EXISTS idx_world_maps_updated_at ON world_maps(updated_at);
                CREATE INDEX IF NOT EXISTS idx_scenes_updated_at ON scenes(updated_at);
                CREATE INDEX IF NOT EXISTS idx_audio_updated_at ON audio_tracks(updated_at);
                CREATE INDEX IF NOT EXISTS idx_resources_updated_at ON resources(updated_at);
                CREATE INDEX IF NOT EXISTS idx_rules_updated_at ON rules(updated_at);
                CREATE INDEX IF NOT EXISTS idx_characters_campaign_slug ON characters(campaign_slug);
                CREATE INDEX IF NOT EXISTS idx_characters_updated_at ON characters(updated_at);
                CREATE INDEX IF NOT EXISTS idx_notes_campaign_slug ON notes(campaign_slug);
                CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at);
                CREATE INDEX IF NOT EXISTS idx_gods_campaign_slug ON gods(campaign_slug);
                CREATE INDEX IF NOT EXISTS idx_gods_updated_at ON gods(updated_at);
                CREATE INDEX IF NOT EXISTS idx_generators_updated_at ON generators(updated_at);
                CREATE INDEX IF NOT EXISTS idx_generator_rows_generator_id ON generator_rows(generator_id, position);
                CREATE INDEX IF NOT EXISTS idx_item_tags_entity ON item_tags(entity_type, item_id);
                CREATE INDEX IF NOT EXISTS idx_item_tags_campaign_slug ON item_tags(campaign_slug);
                CREATE INDEX IF NOT EXISTS idx_item_categories_entity ON item_categories(entity_type, item_id);
                CREATE INDEX IF NOT EXISTS idx_item_categories_campaign_slug ON item_categories(campaign_slug);
                CREATE INDEX IF NOT EXISTS idx_scoped_tag_lists_scope ON scoped_tag_lists(entity_type, scope, campaign_slug, position);
                CREATE INDEX IF NOT EXISTS idx_scoped_category_lists_scope ON scoped_category_lists(entity_type, scope, campaign_slug, position);

                CREATE TRIGGER IF NOT EXISTS trg_rules_spotlight_insert
                AFTER INSERT ON rules
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'rules';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'rules', '', NEW.title, NEW.content || ' ' || NEW.source, 'rules rule РїСЂР°РІРёР»Рѕ ' || NEW.source);
                END;
                CREATE TRIGGER IF NOT EXISTS trg_rules_spotlight_update
                AFTER UPDATE ON rules
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'rules';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'rules', '', NEW.title, NEW.content || ' ' || NEW.source, 'rules rule РїСЂР°РІРёР»Рѕ ' || NEW.source);
                END;
                CREATE TRIGGER IF NOT EXISTS trg_rules_spotlight_delete
                AFTER DELETE ON rules
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = OLD.id AND entity_type = 'rules';
                END;

                CREATE TRIGGER IF NOT EXISTS trg_resources_spotlight_insert
                AFTER INSERT ON resources
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'resources';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'resources', '', NEW.title, NEW.description || ' ' || NEW.source_type || ' ' || NEW.source, 'resources resource СЂРµСЃСѓСЂСЃ ' || NEW.source_type);
                END;
                CREATE TRIGGER IF NOT EXISTS trg_resources_spotlight_update
                AFTER UPDATE ON resources
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'resources';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'resources', '', NEW.title, NEW.description || ' ' || NEW.source_type || ' ' || NEW.source, 'resources resource СЂРµСЃСѓСЂСЃ ' || NEW.source_type);
                END;
                CREATE TRIGGER IF NOT EXISTS trg_resources_spotlight_delete
                AFTER DELETE ON resources
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = OLD.id AND entity_type = 'resources';
                END;

                CREATE TRIGGER IF NOT EXISTS trg_maps_spotlight_insert
                AFTER INSERT ON maps
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'maps';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'maps', NEW.campaign_slug, NEW.title, NEW.original_filename, 'maps map РєР°СЂС‚Р°');
                END;
                CREATE TRIGGER IF NOT EXISTS trg_maps_spotlight_update
                AFTER UPDATE ON maps
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'maps';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'maps', NEW.campaign_slug, NEW.title, NEW.original_filename, 'maps map РєР°СЂС‚Р°');
                END;
                CREATE TRIGGER IF NOT EXISTS trg_maps_spotlight_delete
                AFTER DELETE ON maps
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = OLD.id AND entity_type = 'maps';
                END;

                DROP TRIGGER IF EXISTS trg_scenes_spotlight_insert;
                CREATE TRIGGER trg_scenes_spotlight_insert
                AFTER INSERT ON scenes
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'scenes';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'scenes', '', NEW.title, NEW.title, 'scenes scene СЃС†РµРЅР°');
                END;
                DROP TRIGGER IF EXISTS trg_scenes_spotlight_update;
                CREATE TRIGGER trg_scenes_spotlight_update
                AFTER UPDATE ON scenes
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'scenes';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'scenes', '', NEW.title, NEW.title, 'scenes scene СЃС†РµРЅР°');
                END;
                CREATE TRIGGER IF NOT EXISTS trg_scenes_spotlight_delete
                AFTER DELETE ON scenes
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = OLD.id AND entity_type = 'scenes';
                END;

                CREATE TRIGGER IF NOT EXISTS trg_audio_spotlight_insert
                AFTER INSERT ON audio_tracks
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'audio';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'audio', '', NEW.title, NEW.description || ' ' || NEW.source_type || ' ' || NEW.source, 'audio music РјСѓР·С‹РєР° ' || NEW.source_type);
                END;
                CREATE TRIGGER IF NOT EXISTS trg_audio_spotlight_update
                AFTER UPDATE ON audio_tracks
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'audio';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'audio', '', NEW.title, NEW.description || ' ' || NEW.source_type || ' ' || NEW.source, 'audio music РјСѓР·С‹РєР° ' || NEW.source_type);
                END;
                CREATE TRIGGER IF NOT EXISTS trg_audio_spotlight_delete
                AFTER DELETE ON audio_tracks
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = OLD.id AND entity_type = 'audio';
                END;

                CREATE TRIGGER IF NOT EXISTS trg_characters_spotlight_insert
                AFTER INSERT ON characters
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'characters';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'characters', NEW.campaign_slug, NEW.name, NEW.biography, 'characters character npc РїРµСЂСЃРѕРЅР°Р¶');
                END;
                CREATE TRIGGER IF NOT EXISTS trg_characters_spotlight_update
                AFTER UPDATE ON characters
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'characters';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'characters', NEW.campaign_slug, NEW.name, NEW.biography, 'characters character npc РїРµСЂСЃРѕРЅР°Р¶');
                END;
                CREATE TRIGGER IF NOT EXISTS trg_characters_spotlight_delete
                AFTER DELETE ON characters
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = OLD.id AND entity_type = 'characters';
                END;

                CREATE TRIGGER IF NOT EXISTS trg_notes_spotlight_insert
                AFTER INSERT ON notes
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'notes';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'notes', NEW.campaign_slug, NEW.title, NEW.content, 'notes note Р·Р°РјРµС‚РєР°');
                END;
                CREATE TRIGGER IF NOT EXISTS trg_notes_spotlight_update
                AFTER UPDATE ON notes
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'notes';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.id, 'notes', NEW.campaign_slug, NEW.title, NEW.content, 'notes note Р·Р°РјРµС‚РєР°');
                END;
                CREATE TRIGGER IF NOT EXISTS trg_notes_spotlight_delete
                AFTER DELETE ON notes
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = OLD.id AND entity_type = 'notes';
                END;

                DROP TRIGGER IF EXISTS trg_gods_spotlight_insert;
                CREATE TRIGGER trg_gods_spotlight_insert
                AFTER INSERT ON gods
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'gods';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (
                        NEW.id,
                        'gods',
                        NEW.campaign_slug,
                        NEW.name,
                        NEW.description || ' ' || NEW.alignment || ' ' || NEW.pantheon || ' ' || NEW.symbol || ' ' || NEW.source,
                        'gods god deity бог боги божество пантеон домен ' || NEW.alignment || ' ' || NEW.pantheon
                    );
                END;
                DROP TRIGGER IF EXISTS trg_gods_spotlight_update;
                CREATE TRIGGER trg_gods_spotlight_update
                AFTER UPDATE ON gods
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.id AND entity_type = 'gods';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (
                        NEW.id,
                        'gods',
                        NEW.campaign_slug,
                        NEW.name,
                        NEW.description || ' ' || NEW.alignment || ' ' || NEW.pantheon || ' ' || NEW.symbol || ' ' || NEW.source,
                        'gods god deity бог боги божество пантеон домен ' || NEW.alignment || ' ' || NEW.pantheon
                    );
                END;
                CREATE TRIGGER IF NOT EXISTS trg_gods_spotlight_delete
                AFTER DELETE ON gods
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = OLD.id AND entity_type = 'gods';
                END;

                CREATE TRIGGER IF NOT EXISTS trg_campaigns_spotlight_insert
                AFTER INSERT ON campaigns
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.slug AND entity_type = 'campaigns';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.slug, 'campaigns', NEW.slug, NEW.name, NEW.description, 'campaign РєР°РјРїР°РЅРёСЏ ' || NEW.slug);
                END;
                CREATE TRIGGER IF NOT EXISTS trg_campaigns_spotlight_update
                AFTER UPDATE ON campaigns
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = NEW.slug AND entity_type = 'campaigns';
                    INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                    VALUES (NEW.slug, 'campaigns', NEW.slug, NEW.name, NEW.description, 'campaign РєР°РјРїР°РЅРёСЏ ' || NEW.slug);
                END;
                CREATE TRIGGER IF NOT EXISTS trg_campaigns_spotlight_delete
                AFTER DELETE ON campaigns
                BEGIN
                    DELETE FROM spotlight_search WHERE item_id = OLD.slug AND entity_type = 'campaigns';
                END;

                DROP TRIGGER IF EXISTS trg_generators_spotlight_insert;
                DROP TRIGGER IF EXISTS trg_generators_spotlight_update;
                DROP TRIGGER IF EXISTS trg_generators_spotlight_delete;
                """
            )
            self._ensure_runtime_columns(connection)

    def _ensure_runtime_columns(self, connection: sqlite3.Connection) -> None:
        desired_columns = {
            "campaigns": {
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "maps": {
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "world_maps": {
                "base_map_id": "TEXT NOT NULL DEFAULT ''",
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "scenes": {
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "audio_tracks": {
                "category": "TEXT NOT NULL DEFAULT ''",
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "resources": {
                "category": "TEXT NOT NULL DEFAULT ''",
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "rules": {
                "tag": "TEXT NOT NULL DEFAULT ''",
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "characters": {
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "notes": {
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "gods": {
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
            "generators": {
                "dice_expression": "TEXT NOT NULL DEFAULT '1d20'",
                "category": "TEXT NOT NULL DEFAULT ''",
                "json_payload": "TEXT NOT NULL DEFAULT '{}'",
                "position": "INTEGER NOT NULL DEFAULT 0",
            },
        }
        for table, columns in desired_columns.items():
            existing = {
                str(row["name"])
                for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def load_metadata_list(
        self,
        entity: str,
        scope: str = "shared",
        campaign_slug: str = "",
        fallback: list[dict] | None = None,
    ) -> list[dict]:
        if fallback is None:
            fallback = []
        if entity in self.ENTITY_TABLES:
            rows = self.load_entity_list(entity, scope=scope, campaign_slug=campaign_slug)
            if rows:
                return rows
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM metadata_lists
                WHERE entity = ? AND scope = ? AND campaign_slug = ?
                """,
                (entity, scope, campaign_slug),
            ).fetchone()
        if row is None:
            return fallback
        payload = json.loads(row["payload"])
        return payload if isinstance(payload, list) else fallback

    def get_meta(self, key: str, default: str = "") -> str:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO app_meta(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value)),
            )

    def has_content(self) -> bool:
        with closing(self._connect()) as connection:
            for table in self.ENTITY_TABLES.values():
                count = connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
                if int(count) > 0:
                    return True
        return False

    def clear_legacy_payload_tables(self) -> None:
        with self._transaction() as connection:
            connection.execute("DELETE FROM metadata_lists")
            connection.execute("DELETE FROM label_lists")

    def save_metadata_list(
        self,
        entity: str,
        payload: list[dict],
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> None:
        if entity in self.ENTITY_TABLES:
            self.save_entity_list(entity, payload, scope=scope, campaign_slug=campaign_slug)
            return
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO metadata_lists(entity, scope, campaign_slug, payload, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(entity, scope, campaign_slug)
                DO UPDATE SET payload = excluded.payload, updated_at = datetime('now')
                """,
                (entity, scope, campaign_slug, serialized),
            )
            self._sync_metadata_spotlight(connection, entity, payload, scope=scope, campaign_slug=campaign_slug)

    def load_entity_list(self, entity: str, scope: str = "shared", campaign_slug: str = "") -> list[dict]:
        if entity == "generators":
            return self.load_generators()
        table = self.ENTITY_TABLES[entity]
        identity_column = "slug" if entity == "campaigns" else "id"
        conditions = []
        params: list[Any] = []
        if entity == "maps":
            conditions.append("scope = ?")
            params.append(scope)
            conditions.append("campaign_slug = ?")
            params.append(campaign_slug if scope == "campaign" else "")
        elif entity in {"world_maps", "characters", "notes", "gods"}:
            conditions.append("campaign_slug = ?")
            params.append(campaign_slug)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT {identity_column}, json_payload FROM {table} {where} ORDER BY position ASC, rowid ASC",
                params,
            ).fetchall()
        items = []
        for row in rows:
            items.append(
                self._decode_json_object(
                    entity,
                    str(row[identity_column]),
                    row["json_payload"],
                )
            )
        return items

    def save_entity_list(
        self,
        entity: str,
        payload: list[dict],
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> None:
        if entity == "generators":
            self.save_generators(payload)
            return
        table = self.ENTITY_TABLES[entity]
        with self._transaction() as connection:
            if entity == "campaigns":
                invalid_items = [
                    item
                    for item in payload
                    if not isinstance(item, dict) or not str(item.get("slug") or "").strip()
                ]
                if invalid_items:
                    raise ValueError("Campaign bulk upsert requires a slug for every item.")
            else:
                self._delete_entity_scope(connection, entity, scope=scope, campaign_slug=campaign_slug)
            for position, item in enumerate(payload):
                if not isinstance(item, dict):
                    continue
                values = self._entity_row_values(entity, item, position, scope=scope, campaign_slug=campaign_slug)
                self._upsert_entity_row(connection, entity, values)
            self._sync_metadata_spotlight(connection, entity, payload, scope=scope, campaign_slug=campaign_slug)

    def save_entity_item(
        self,
        entity: str,
        item: dict,
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> None:
        if entity not in self.ENTITY_TABLES or entity == "generators":
            raise ValueError(f"Unsupported single-item save for entity: {entity}")
        if not isinstance(item, dict):
            raise ValueError("Single-item save expects a dictionary payload.")

        table = self.ENTITY_TABLES[entity]
        identity_column = "slug" if entity == "campaigns" else "id"
        item_id = str(item.get(identity_column) or item.get("id") or item.get("slug") or "").strip()
        if not item_id:
            raise ValueError(f"Cannot save {entity} item without an id.")

        with self._transaction() as connection:
            existing = connection.execute(
                f"SELECT position FROM {table} WHERE {identity_column} = ?",
                (item_id,),
            ).fetchone()
            if existing is not None:
                position = int(existing["position"])
            else:
                position = int(connection.execute(
                    f"SELECT COALESCE(MAX(position), -1) + 1 AS position FROM {table}",
                ).fetchone()["position"])

            values = self._entity_row_values(entity, item, position, scope=scope, campaign_slug=campaign_slug)
            self._upsert_entity_row(connection, entity, values)
            self._sync_metadata_spotlight_item(connection, entity, item, scope=scope, campaign_slug=campaign_slug)

    def delete_entity_item(
        self,
        entity: str,
        item_id: str,
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> bool:
        if entity not in self.ENTITY_TABLES or entity == "generators":
            raise ValueError(f"Unsupported single-item delete for entity: {entity}")
        clean_id = str(item_id or "").strip()
        if not clean_id:
            return False

        table = self.ENTITY_TABLES[entity]
        identity_column = "slug" if entity == "campaigns" else "id"
        with self._transaction() as connection:
            cursor = connection.execute(
                f"DELETE FROM {table} WHERE {identity_column} = ?",
                (clean_id,),
            )
            indexed_campaign_slug = campaign_slug if scope == "campaign" or entity in {"characters", "notes", "gods"} else ""
            connection.execute(
                "DELETE FROM spotlight_search WHERE item_id = ? AND entity_type = ? AND campaign_slug = ?",
                (clean_id, entity, indexed_campaign_slug),
            )
        return cursor.rowcount > 0

    def replace_rule_field_value(
        self,
        field: str,
        old_value: str,
        new_value: str,
        updated_at: str,
    ) -> list[str]:
        if field not in {"tag", "source"}:
            raise ValueError(f"Unsupported rule field replacement: {field}")

        old_key = str(old_value or "").strip().casefold()
        if not old_key:
            return []

        moved_rule_ids: list[str] = []
        with self._transaction() as connection:
            rows = connection.execute(
                f"SELECT id, {field} AS current_value, json_payload FROM rules"
            ).fetchall()
            for row in rows:
                current_value = str(row["current_value"] or "").strip()
                if current_value.casefold() != old_key:
                    continue
                item = self._decode_json_object(
                    "rules",
                    str(row["id"]),
                    row["json_payload"],
                )
                item["id"] = str(item.get("id") or row["id"])
                item[field] = new_value
                item["updated_at"] = updated_at
                serialized = json.dumps(item, ensure_ascii=False, indent=2)
                connection.execute(
                    f"UPDATE rules SET {field} = ?, updated_at = ?, json_payload = ? WHERE id = ?",
                    (new_value, updated_at, serialized, row["id"]),
                )
                self._sync_metadata_spotlight_item(connection, "rules", item, scope="shared")
                moved_rule_ids.append(str(row["id"]))
        return moved_rule_ids

    def load_generators(self) -> list[dict]:
        with closing(self._connect()) as connection:
            generator_rows = connection.execute(
                """
                SELECT id, title, description, dice_expression, category, created_at, updated_at, position, json_payload
                FROM generators
                ORDER BY position ASC, rowid ASC
                """
            ).fetchall()
            table_rows = connection.execute(
                """
                SELECT id, generator_id, range_min, range_max, result_markdown, position
                FROM generator_rows
                ORDER BY generator_id ASC, position ASC, range_min ASC
                """
            ).fetchall()
            tag_rows = connection.execute(
                """
                SELECT item_tags.item_id, tags.name
                FROM item_tags
                JOIN tags ON tags.id = item_tags.tag_id
                WHERE item_tags.entity_type = 'generators'
                ORDER BY tags.name COLLATE NOCASE ASC
                """
            ).fetchall()
        rows_by_generator: dict[str, list[dict]] = {}
        for row in table_rows:
            rows_by_generator.setdefault(str(row["generator_id"]), []).append(
                {
                    "id": str(row["id"]),
                    "min": int(row["range_min"]),
                    "max": int(row["range_max"]),
                    "result_markdown": str(row["result_markdown"] or ""),
                }
            )
        tags_by_generator: dict[str, list[str]] = {}
        for row in tag_rows:
            tags_by_generator.setdefault(str(row["item_id"]), []).append(str(row["name"]))

        items = []
        for row in generator_rows:
            item = self._decode_json_object(
                "generators",
                str(row["id"]),
                row["json_payload"],
            )
            generator_id = str(row["id"])
            item.update(
                {
                    "id": generator_id,
                    "title": str(row["title"] or ""),
                    "description": str(row["description"] or ""),
                    "dice_expression": str(row["dice_expression"] or "1d20"),
                    "category": str(row["category"] or ""),
                    "tags": tags_by_generator.get(generator_id, []),
                    "rows": rows_by_generator.get(generator_id, []),
                    "created_at": str(row["created_at"] or ""),
                    "updated_at": str(row["updated_at"] or ""),
                }
            )
            items.append(item)
        return items

    def load_generator(self, generator_id: str) -> dict | None:
        generator_id = str(generator_id or "").strip()
        if not generator_id:
            return None
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT id, title, description, dice_expression, category, created_at, updated_at, position, json_payload
                FROM generators
                WHERE id = ?
                """,
                (generator_id,),
            ).fetchone()
            if row is None:
                return None
            table_rows = connection.execute(
                """
                SELECT id, range_min, range_max, result_markdown, position
                FROM generator_rows
                WHERE generator_id = ?
                ORDER BY position ASC, range_min ASC
                """,
                (generator_id,),
            ).fetchall()
            tag_rows = connection.execute(
                """
                SELECT tags.name
                FROM item_tags
                JOIN tags ON tags.id = item_tags.tag_id
                WHERE item_tags.entity_type = 'generators' AND item_tags.item_id = ?
                ORDER BY tags.name COLLATE NOCASE ASC
                """,
                (generator_id,),
            ).fetchall()
        item = self._decode_json_object(
            "generators",
            str(row["id"]),
            row["json_payload"],
        )
        item.update(
            {
                "id": str(row["id"]),
                "title": str(row["title"] or ""),
                "description": str(row["description"] or ""),
                "dice_expression": str(row["dice_expression"] or "1d20"),
                "category": str(row["category"] or ""),
                "tags": [str(tag["name"]) for tag in tag_rows],
                "rows": [
                    {
                        "id": str(table_row["id"]),
                        "min": int(table_row["range_min"]),
                        "max": int(table_row["range_max"]),
                        "result_markdown": str(table_row["result_markdown"] or ""),
                    }
                    for table_row in table_rows
                ],
                "created_at": str(row["created_at"] or ""),
                "updated_at": str(row["updated_at"] or ""),
            }
        )
        return item

    def save_generators(self, generators: list[dict]) -> None:
        with self._transaction() as connection:
            connection.execute("DELETE FROM item_tags WHERE entity_type = 'generators'")
            connection.execute("DELETE FROM generator_rows")
            connection.execute("DELETE FROM generators")
            for position, item in enumerate(generators):
                if not isinstance(item, dict):
                    continue
                values = self._entity_row_values("generators", item, position)
                connection.execute(
                    """
                    INSERT INTO generators(
                        id, title, description, dice_expression, category,
                        created_at, updated_at, json_payload, position
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        values["id"],
                        values["title"],
                        values["description"],
                        values["dice_expression"],
                        values["category"],
                        values["created_at"],
                        values["updated_at"],
                        values["json_payload"],
                        values["position"],
                    ],
                )
                for row_position, table_row in enumerate(item.get("rows") or []):
                    if not isinstance(table_row, dict):
                        continue
                    row_id = str(table_row.get("id") or "").strip()
                    if not row_id:
                        continue
                    connection.execute(
                        """
                        INSERT INTO generator_rows(
                            id, generator_id, range_min, range_max, result_markdown, position
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row_id,
                            values["id"],
                            int(table_row.get("min", table_row.get("range_min", 0))),
                            int(table_row.get("max", table_row.get("range_max", 0))),
                            str(table_row.get("result_markdown") or table_row.get("result") or ""),
                            row_position,
                        ),
                    )
                for tag in item.get("tags") or []:
                    value = str(tag or "").strip()
                    if not value:
                        continue
                    tag_id = self._ensure_tag(connection, value)
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO item_tags(entity_type, item_id, tag_id, campaign_slug)
                        VALUES ('generators', ?, ?, '')
                        """,
                        (values["id"], tag_id),
                    )
            self._sync_metadata_spotlight(connection, "generators", generators, scope="shared", campaign_slug="")
    def _delete_entity_scope(
        self,
        connection: sqlite3.Connection,
        entity: str,
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> None:
        if entity == "campaigns":
            raise RuntimeError(
                "Campaign collections must be synchronized without deleting retained campaigns."
            )
        table = self.ENTITY_TABLES[entity]
        if entity == "maps":
            connection.execute(
                f"DELETE FROM {table} WHERE scope = ? AND campaign_slug = ?",
                (scope, campaign_slug if scope == "campaign" else ""),
            )
            return
        if entity in {"world_maps", "characters", "notes", "gods"}:
            connection.execute(f"DELETE FROM {table} WHERE campaign_slug = ?", (campaign_slug,))
            return
        connection.execute(f"DELETE FROM {table}")

    def _upsert_entity_row(
        self,
        connection: sqlite3.Connection,
        entity: str,
        values: dict[str, Any],
    ) -> None:
        table = self.ENTITY_TABLES[entity]
        columns = self.ENTITY_TABLE_COLUMNS[entity]
        identity_column = "slug" if entity == "campaigns" else "id"
        placeholders = ",".join("?" for _ in columns)
        update_columns = [column for column in columns if column != identity_column]
        assignments = ",".join(f"{column} = excluded.{column}" for column in update_columns)
        connection.execute(
            f"""
            INSERT INTO {table}({','.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT({identity_column}) DO UPDATE SET {assignments}
            """,
            [values[column] for column in columns],
        )

    def _entity_row_values(
        self,
        entity: str,
        item: dict,
        position: int,
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> dict[str, Any]:
        payload = json.dumps(item, ensure_ascii=False, indent=2)
        now = str(item.get("updated_at") or item.get("created_at") or item.get("uploaded_at") or "")
        item_id = str(item.get("id") or item.get("slug") or "").strip()
        base = {
            "id": item_id,
            "slug": str(item.get("slug") or item_id).strip(),
            "scope": scope,
            "campaign_slug": campaign_slug if scope == "campaign" or entity in {"world_maps", "characters", "notes", "gods"} else "",
            "title": str(item.get("title") or item.get("name") or item.get("filename") or item_id).strip(),
            "base_map_id": str(item.get("base_map_id") or "").strip(),
            "name": str(item.get("name") or item.get("title") or item_id).strip(),
            "description": str(item.get("description") or "").strip(),
            "system": str(item.get("system") or "").strip(),
            "foundry_slug": str(item.get("foundry_slug") or item.get("slug") or "").strip(),
            "cover_image": str(item.get("cover_image") or "").strip(),
            "filename": str(item.get("filename") or item.get("image") or "").strip(),
            "original_filename": str(item.get("original_filename") or "").strip(),
            "file_path": str(item.get("file_path") or item.get("source") or item.get("url") or "").strip(),
            "source_type": str(item.get("source_type") or "").strip(),
            "source": str(item.get("source") or item.get("url") or "").strip(),
            "category": str(item.get("category") or "").strip(),
            "content": str(item.get("content") or item.get("body") or "").strip(),
            "description": str(item.get("description") or item.get("body") or "").strip(),
            "tag": str(item.get("tag") or "").strip(),
            "race": str(item.get("race") or "").strip(),
            "gender": str(item.get("gender") or "").strip(),
            "attitude": str(item.get("attitude") or "").strip(),
            "appearance": str(item.get("appearance") or "").strip(),
            "biography": str(item.get("biography") or "").strip(),
            "notes": str(item.get("notes") or "").strip(),
            "image": str(item.get("image") or item.get("filename") or "").strip(),
            "session_no": self._safe_int(item.get("session_number", item.get("number", 0))),
            "status": str(item.get("status") or "").strip(),
            "note_type": str(item.get("type") or "").strip(),
            "alignment": str(item.get("alignment") or "").strip(),
            "pantheon": str(item.get("pantheon") or "").strip(),
            "symbol": str(item.get("symbol") or "").strip(),
            "dice_expression": str(item.get("dice_expression") or "1d20").strip(),
            "uploaded_at": str(item.get("uploaded_at") or "").strip(),
            "created_at": str(item.get("created_at") or now).strip(),
            "updated_at": str(item.get("updated_at") or now).strip(),
            "json_payload": payload,
            "position": int(position),
        }
        return base

    def _safe_int(self, value: Any, fallback: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _decode_json_object(self, entity: str, item_id: str, raw_payload: Any) -> dict:
        try:
            item = json.loads(raw_payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise DataIntegrityError(
                f"Corrupt json_payload for {entity}:{item_id}; the database row was preserved."
            ) from exc
        if not isinstance(item, dict):
            raise DataIntegrityError(
                f"Invalid json_payload type for {entity}:{item_id}; expected an object and preserved the row."
            )
        return item

    def _sync_metadata_spotlight(
        self,
        connection: sqlite3.Connection,
        entity: str,
        payload: list[dict],
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> None:
        if entity not in {"maps", "scenes", "audio", "resources", "rules", "characters", "notes", "gods", "generators"}:
            return

        indexed_campaign_slug = campaign_slug if scope == "campaign" or entity in {"characters", "notes", "gods"} else ""
        connection.execute(
            "DELETE FROM spotlight_search WHERE entity_type = ? AND campaign_slug = ?",
            (entity, indexed_campaign_slug),
        )
        for item in payload:
            if not isinstance(item, dict):
                continue
            row = self._metadata_spotlight_row(entity, item, indexed_campaign_slug)
            if row is None:
                continue
            connection.execute(
                """
                INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                row,
            )

    def _sync_metadata_spotlight_item(
        self,
        connection: sqlite3.Connection,
        entity: str,
        item: dict,
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> None:
        if entity not in {"maps", "scenes", "audio", "resources", "rules", "characters", "notes", "gods", "generators"}:
            return
        indexed_campaign_slug = campaign_slug if scope == "campaign" or entity in {"characters", "notes", "gods"} else ""
        row = self._metadata_spotlight_row(entity, item, indexed_campaign_slug)
        if row is None:
            return
        connection.execute(
            "DELETE FROM spotlight_search WHERE item_id = ? AND entity_type = ? AND campaign_slug = ?",
            (row[0], entity, indexed_campaign_slug),
        )
        connection.execute(
            """
            INSERT INTO spotlight_search(item_id, entity_type, campaign_slug, title, body, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            row,
        )

    def _metadata_spotlight_row(
        self,
        entity: str,
        item: dict,
        campaign_slug: str,
    ) -> tuple[str, str, str, str, str, str] | None:
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            return None

        title = str(item.get("title") or item.get("name") or item.get("filename") or item_id).strip()
        tags = self._stringify_search_parts(item.get("tags"), item.get("tag"), item.get("category"), item.get("source"))
        if entity == "notes":
            body = self._stringify_search_parts(
                item.get("body"),
                item.get("content"),
                item.get("planned_body"),
                item.get("happened_body"),
                item.get("status"),
                item.get("world_date"),
            )
        elif entity == "characters":
            body = self._stringify_search_parts(
                item.get("race"),
                item.get("gender"),
                item.get("attitude"),
                item.get("appearance"),
                item.get("biography"),
                item.get("notes"),
            )
        elif entity == "gods":
            tags = self._stringify_search_parts(
                item.get("domains"),
                item.get("alignment"),
                item.get("pantheon"),
                item.get("pantheons"),
                item.get("rank"),
                item.get("source"),
            )
            body = self._stringify_search_parts(
                item.get("description"),
                item.get("name_eng"),
                item.get("english_name"),
                item.get("alignment"),
                item.get("domains"),
                item.get("pantheon"),
                item.get("pantheons"),
                item.get("rank"),
                item.get("titles"),
                item.get("symbol"),
                item.get("source"),
            )
        elif entity == "generators":
            tags = self._stringify_search_parts(tags, "generators", "generator", "генератор", "таблица")
            body = self._stringify_search_parts(
                item.get("description"),
                item.get("dice_expression"),
                item.get("category"),
                [
                    row.get("result_markdown", "")
                    for row in item.get("rows", [])
                    if isinstance(row, dict)
                ],
            )
        else:
            body_parts = [
                item.get("description"),
                item.get("content"),
                item.get("source"),
                item.get("url"),
            ]
            if entity != "scenes":
                body_parts.extend([item.get("filename"), item.get("original_filename")])
            body = self._stringify_search_parts(*body_parts)
        return (item_id, entity, campaign_slug, title, body, tags)

    def _stringify_search_parts(self, *parts: Any) -> str:
        values: list[str] = []
        for part in parts:
            if part is None:
                continue
            if isinstance(part, (list, tuple, set)):
                values.extend(str(item) for item in part if item is not None)
                continue
            values.append(str(part))
        return " ".join(value.strip() for value in values if value and value.strip())

    def load_label_list(
        self,
        label_type: str,
        scope: str = "shared",
        campaign_slug: str = "",
        fallback: list[str] | None = None,
    ) -> list[str]:
        if fallback is None:
            fallback = []
        labels = self.load_ordered_labels(label_type, scope=scope, campaign_slug=campaign_slug)
        if labels:
            return labels
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM label_lists
                WHERE label_type = ? AND scope = ? AND campaign_slug = ?
                """,
                (label_type, scope, campaign_slug),
            ).fetchone()
        if row is None:
            return fallback
        payload = json.loads(row["payload"])
        if not isinstance(payload, list):
            return fallback
        return [str(item) for item in payload]

    def save_label_list(
        self,
        label_type: str,
        payload: list[str],
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> None:
        self.save_ordered_labels(label_type, payload, scope=scope, campaign_slug=campaign_slug)
        return
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO label_lists(label_type, scope, campaign_slug, payload, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(label_type, scope, campaign_slug)
                DO UPDATE SET payload = excluded.payload, updated_at = datetime('now')
                """,
                (label_type, scope, campaign_slug, serialized),
            )

    def load_ordered_labels(self, label_type: str, scope: str = "shared", campaign_slug: str = "") -> list[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT tags.name
                FROM scoped_tag_lists
                JOIN tags ON tags.id = scoped_tag_lists.tag_id
                WHERE scoped_tag_lists.entity_type = ?
                  AND scoped_tag_lists.scope = ?
                  AND scoped_tag_lists.campaign_slug = ?
                ORDER BY scoped_tag_lists.position ASC, tags.name COLLATE NOCASE ASC
                """,
                (label_type, scope, campaign_slug),
            ).fetchall()
        labels = [str(row["name"]) for row in rows]
        return labels

    def save_ordered_labels(
        self,
        label_type: str,
        labels: list[str],
        scope: str = "shared",
        campaign_slug: str = "",
    ) -> None:
        normalized = []
        seen = set()
        for label in labels or []:
            value = str(label or "").strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(value)
        with self._transaction() as connection:
            connection.execute(
                "DELETE FROM scoped_tag_lists WHERE entity_type = ? AND scope = ? AND campaign_slug = ?",
                (label_type, scope, campaign_slug),
            )
            for position, label in enumerate(normalized):
                tag_id = self._ensure_tag(connection, label)
                connection.execute(
                    """
                    INSERT OR REPLACE INTO scoped_tag_lists(entity_type, scope, campaign_slug, tag_id, position)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (label_type, scope, campaign_slug, tag_id, position),
                )
    def _ensure_tag(self, connection: sqlite3.Connection, name: str) -> int:
        connection.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))
        row = connection.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        return int(row["id"])

    def table_counts(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            metadata_count = connection.execute("SELECT COUNT(*) AS count FROM metadata_lists").fetchone()["count"]
            labels_count = connection.execute("SELECT COUNT(*) AS count FROM label_lists").fetchone()["count"]
            entity_counts = {
                entity: connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
                for entity, table in self.ENTITY_TABLES.items()
            }
        return {"metadata_lists": metadata_count, "label_lists": labels_count, **entity_counts}

    def search_spotlight(
        self,
        query: str,
        entity_types: list[str] | None = None,
        campaign_slug: str = "",
        limit: int = 100,
    ) -> list[dict]:
        prepared_query = (query or "").strip()
        if not prepared_query:
            return []
        fts_query = self._build_fts_query(prepared_query)
        def ranked(rows: list[sqlite3.Row]) -> list[dict]:
            needle = prepared_query.casefold()

            def score(row: sqlite3.Row) -> tuple[int, int]:
                title = str(row["title"] or "").casefold()
                tags = str(row["tags"] or "").casefold()
                body = str(row["body"] or "").casefold()
                if title == needle:
                    rank = 0
                elif title.startswith(needle):
                    rank = 1
                elif needle in title:
                    rank = 2
                elif needle in tags:
                    rank = 3
                elif needle in body:
                    rank = 4
                else:
                    rank = 5
                return (rank, len(title))

            return [dict(row) for row in sorted(rows, key=score)]

        params: list[Any] = [fts_query]
        conditions = ["spotlight_search MATCH ?"]
        if entity_types:
            placeholders = ",".join("?" for _ in entity_types)
            conditions.append(f"entity_type IN ({placeholders})")
            params.extend(entity_types)
        if campaign_slug:
            conditions.append("campaign_slug = ?")
            params.append(campaign_slug)
        params.extend([prepared_query, f"{prepared_query}%", prepared_query, prepared_query, prepared_query])
        params.append(int(limit))
        sql = f"""
            SELECT item_id, entity_type, campaign_slug, title, body, tags
            FROM spotlight_search
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE
                    WHEN lower(title) = lower(?) THEN 0
                    WHEN lower(title) LIKE lower(?) THEN 1
                    WHEN instr(lower(title), lower(?)) > 0 THEN 2
                    WHEN instr(lower(tags), lower(?)) > 0 THEN 3
                    WHEN instr(lower(body), lower(?)) > 0 THEN 4
                    ELSE 5
                END,
                bm25(spotlight_search, 6.0, 2.6, 1.0)
            LIMIT ?
        """
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, params).fetchall()
            if rows:
                return ranked(rows)

            alias_query = self._alias_query(prepared_query)
            if alias_query:
                retry_params: list[Any] = [alias_query]
                retry_conditions = ["spotlight_search MATCH ?"]
                if entity_types:
                    placeholders = ",".join("?" for _ in entity_types)
                    retry_conditions.append(f"entity_type IN ({placeholders})")
                    retry_params.extend(entity_types)
                if campaign_slug:
                    retry_conditions.append("campaign_slug = ?")
                    retry_params.append(campaign_slug)
                retry_params.extend([prepared_query, f"{prepared_query}%", prepared_query, prepared_query, prepared_query])
                retry_params.append(int(limit))
                retry_sql = f"""
                    SELECT item_id, entity_type, campaign_slug, title, body, tags
                    FROM spotlight_search
                    WHERE {' AND '.join(retry_conditions)}
                    ORDER BY
                        CASE
                            WHEN lower(title) = lower(?) THEN 0
                            WHEN lower(title) LIKE lower(?) THEN 1
                            WHEN instr(lower(title), lower(?)) > 0 THEN 2
                            WHEN instr(lower(tags), lower(?)) > 0 THEN 3
                            WHEN instr(lower(body), lower(?)) > 0 THEN 4
                            ELSE 5
                        END,
                        bm25(spotlight_search, 6.0, 2.6, 1.0)
                    LIMIT ?
                """
                rows = connection.execute(retry_sql, retry_params).fetchall()
                if rows:
                    return ranked(rows)

            like_value = f"%{prepared_query.lower()}%"
            fallback_params: list[Any] = []
            fallback_conditions = ["(lower(title) LIKE ? OR lower(body) LIKE ? OR lower(tags) LIKE ?)"]
            fallback_params.extend([like_value, like_value, like_value])
            if entity_types:
                placeholders = ",".join("?" for _ in entity_types)
                fallback_conditions.append(f"entity_type IN ({placeholders})")
                fallback_params.extend(entity_types)
            if campaign_slug:
                fallback_conditions.append("campaign_slug = ?")
                fallback_params.append(campaign_slug)
            fallback_params.extend([prepared_query, f"{prepared_query}%", prepared_query, prepared_query, prepared_query])
            fallback_params.append(int(limit))
            fallback_sql = f"""
                SELECT item_id, entity_type, campaign_slug, title, body, tags
                FROM spotlight_search
                WHERE {' AND '.join(fallback_conditions)}
                ORDER BY
                    CASE
                        WHEN lower(title) = lower(?) THEN 0
                        WHEN lower(title) LIKE lower(?) THEN 1
                        WHEN instr(lower(title), lower(?)) > 0 THEN 2
                        WHEN instr(lower(tags), lower(?)) > 0 THEN 3
                        WHEN instr(lower(body), lower(?)) > 0 THEN 4
                        ELSE 5
                    END,
                    length(title) ASC
                LIMIT ?
            """
            rows = connection.execute(fallback_sql, fallback_params).fetchall()
            return ranked(rows)

    def _build_fts_query(self, query: str) -> str:
        tokens = re.findall(r"\w+", query.strip(), flags=re.UNICODE)
        if not tokens:
            return ""
        if len(tokens) > 1:
            return " ".join(f"{token}*" if len(token) >= 3 else token for token in tokens)
        token = tokens[0]
        # Prefix-search for single-token queries (including Cyrillic),
        # so "Р‘Р°РЅРґРёС‚СЃ" matches "Р‘Р°РЅРґРёС‚СЃРєРёРµ".
        if len(token) >= 3:
            return f"{token}*"
        return token

    def _alias_query(self, query: str) -> str:
        aliases = {
            "xge": "xge OR xanathar OR xanathars",
            "phb": "phb OR player OR handbook",
            "dmg": "dmg OR dungeon OR master OR guide",
            "mm": "mm OR monster OR manual",
            "tce": "tce OR tasha",
            "notes": "notes OR note OR Р·Р°РјРµС‚РєР° OR Р·Р°РјРµС‚РєРё",
            "note": "note OR notes OR Р·Р°РјРµС‚РєР° OR Р·Р°РјРµС‚РєРё",
            "Р±РёРѕРіСЂР°С„РёСЏ": "Р±РёРѕРіСЂР°С„РёСЏ OR biography OR РїРµСЂСЃРѕРЅР°Р¶ OR npc",
            "biography": "biography OR Р±РёРѕРіСЂР°С„РёСЏ OR character OR npc",
        }
        return aliases.get(query.strip().lower(), "")
