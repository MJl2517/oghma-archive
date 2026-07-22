from pathlib import Path

from ogma.foundry import normalize_foundry_relative_path
from ogma.safe_paths import PathBoundaryError
from ogma.json_store import read_json, write_json


THEME_OPTIONS = {
    "madness-crown": "\u041a\u043e\u0440\u043e\u043d\u0430 \u0431\u0435\u0437\u0443\u043c\u0438\u044f",
    "frost-ray": "\u041b\u0443\u0447 \u0425\u043e\u043b\u043e\u0434\u0430",
    "hadar-hunger": "\u0413\u043e\u043b\u043e\u0434 \u0425\u0430\u0434\u0430\u0440\u0430",
    "goodberry": "\u0414\u043e\u0431\u0440\u044f\u043d\u0438\u043a\u0430",
    "shield-faith": "\u0429\u0438\u0442 \u0432\u0435\u0440\u044b",
}


def clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


class SettingsStore:
    def __init__(
        self,
        data_dir: Path,
        settings_path: Path,
        default_foundry_data_dir: str,
        default_foundry_assets_dir: str,
        spotlight_material_options: list[str],
    ) -> None:
        self.data_dir = data_dir
        self.settings_path = settings_path
        self.default_foundry_data_dir = default_foundry_data_dir
        self.default_foundry_assets_dir = default_foundry_assets_dir
        self.spotlight_material_options = spotlight_material_options

    def default(self) -> dict:
        return {
            "foundry": {
                "enabled": True,
                "data_dir": self.default_foundry_data_dir,
                "assets_dir": self.default_foundry_assets_dir,
            },
            "spotlight": {
                "materials": self.spotlight_material_options[:],
                "campaigns": [],
                "campaign_mode": "all",
            },
            "favorites": {
                "campaign_slug": "",
                "active_group_id": "default",
                "groups": [
                    {
                        "id": "default",
                        "name": "Основное",
                        "items": [],
                    }
                ],
            },
            "demo": {
                "enabled": False,
            },
            "appearance": {
                "theme": "madness-crown",
            },
            "notifications": {
                "session_reminders_enabled": True,
                "session_reminder_days": 3,
                "session_reminder_interval_hours": 12,
            },
        }

    def merge(self, settings: dict) -> dict:
        merged = self.default()
        foundry = settings.get("foundry", {}) if isinstance(settings, dict) else {}
        spotlight = settings.get("spotlight", {}) if isinstance(settings, dict) else {}
        try:
            assets_dir = normalize_foundry_relative_path(
                str(foundry.get("assets_dir", merged["foundry"]["assets_dir"])).strip()
                or self.default_foundry_assets_dir
            )
        except PathBoundaryError:
            assets_dir = normalize_foundry_relative_path(self.default_foundry_assets_dir)
        merged["foundry"].update(
            {
                "enabled": bool(foundry.get("enabled", merged["foundry"]["enabled"])),
                "data_dir": str(foundry.get("data_dir", merged["foundry"]["data_dir"])).strip(),
                "assets_dir": assets_dir,
            }
        )
        spotlight_materials = spotlight.get("materials", merged["spotlight"]["materials"])
        if not isinstance(spotlight_materials, list):
            spotlight_materials = merged["spotlight"]["materials"]
        selected_materials = [
            option for option in self.spotlight_material_options if option in spotlight_materials
        ]
        if (
            "gods" in self.spotlight_material_options
            and "gods" not in selected_materials
            and all(option == "gods" or option in selected_materials for option in self.spotlight_material_options)
        ):
            selected_materials.append("gods")
        merged["spotlight"]["materials"] = selected_materials or self.spotlight_material_options[:]

        spotlight_campaigns = spotlight.get("campaigns", merged["spotlight"]["campaigns"])
        if not isinstance(spotlight_campaigns, list):
            spotlight_campaigns = []
        merged["spotlight"]["campaigns"] = [str(slug).strip() for slug in spotlight_campaigns if str(slug).strip()]
        campaign_mode = str(spotlight.get("campaign_mode", merged["spotlight"]["campaign_mode"])).strip().lower()
        merged["spotlight"]["campaign_mode"] = "selected" if campaign_mode == "selected" else "all"
        favorites = settings.get("favorites", {}) if isinstance(settings, dict) else {}
        merged["favorites"]["campaign_slug"] = str(
            favorites.get("campaign_slug", merged["favorites"]["campaign_slug"])
        ).strip()
        groups = favorites.get("groups", merged["favorites"]["groups"])
        if not isinstance(groups, list):
            groups = []
        normalized_groups = []
        seen_group_ids = set()
        for index, group in enumerate(groups):
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("id", "")).strip() or ("default" if index == 0 else "")
            if not group_id or group_id in seen_group_ids:
                continue
            seen_group_ids.add(group_id)
            items = group.get("items", [])
            if not isinstance(items, list):
                items = []
            normalized_items = []
            seen_items = set()
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_type = str(item.get("type", "")).strip()
                item_id = str(item.get("id", "")).strip()
                campaign_slug = str(item.get("campaign_slug", "")).strip()
                if not item_type or not item_id:
                    continue
                item_key = (item_type, item_id, campaign_slug)
                if item_key in seen_items:
                    continue
                seen_items.add(item_key)
                normalized_items.append(
                    {
                        "type": item_type,
                        "id": item_id,
                        "campaign_slug": campaign_slug,
                        "added_at": str(item.get("added_at", "")).strip(),
                    }
                )
            normalized_groups.append(
                {
                    "id": group_id,
                    "name": str(group.get("name", "")).strip() or "Основное",
                    "items": normalized_items,
                }
            )
        if not normalized_groups:
            normalized_groups = merged["favorites"]["groups"]
        active_group_id = str(favorites.get("active_group_id", "")).strip()
        if active_group_id not in {group["id"] for group in normalized_groups}:
            active_group_id = normalized_groups[0]["id"]
        merged["favorites"]["active_group_id"] = active_group_id
        merged["favorites"]["groups"] = normalized_groups
        demo = settings.get("demo", {}) if isinstance(settings, dict) else {}
        merged["demo"]["enabled"] = bool(demo.get("enabled", merged["demo"]["enabled"]))
        appearance = settings.get("appearance", {}) if isinstance(settings, dict) else {}
        theme = str(appearance.get("theme", merged["appearance"]["theme"])).strip()
        merged["appearance"]["theme"] = theme if theme in THEME_OPTIONS else "madness-crown"
        notifications = settings.get("notifications", {}) if isinstance(settings, dict) else {}
        merged["notifications"] = {
            "session_reminders_enabled": bool(
                notifications.get(
                    "session_reminders_enabled",
                    merged["notifications"]["session_reminders_enabled"],
                )
            ),
            "session_reminder_days": clamp_int(
                notifications.get("session_reminder_days"),
                merged["notifications"]["session_reminder_days"],
                0,
                30,
            ),
            "session_reminder_interval_hours": clamp_int(
                notifications.get("session_reminder_interval_hours"),
                merged["notifications"]["session_reminder_interval_hours"],
                1,
                168,
            ),
        }
        return merged

    def load(self) -> dict:
        return self.merge(read_json(self.settings_path, fallback={}))

    def save(self, settings: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.settings_path, self.merge(settings))

    def foundry(self) -> dict:
        return self.load()["foundry"]

    def foundry_data_dir(self) -> Path:
        return Path(self.foundry()["data_dir"])

    def foundry_assets_dir(self) -> str:
        return normalize_foundry_relative_path(self.foundry()["assets_dir"] or self.default_foundry_assets_dir)
