from pathlib import Path
import subprocess

from ogma.errors import ValidationError
from ogma.safe_paths import (
    PathBoundaryError,
    normalize_relative_path,
    resolve_destination_under,
)
from ogma.settings_store import THEME_OPTIONS


FOUNDRY_DATA_TITLE = "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043a\u0430\u0442\u0430\u043b\u043e\u0433 Foundry Data"
FOUNDRY_ASSETS_TITLE = "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0430\u043f\u043a\u0443 \u0430\u0441\u0441\u0435\u0442\u043e\u0432 \u0432\u043d\u0443\u0442\u0440\u0438 Foundry Data"
FOUNDRY_ASSETS_OUTSIDE_ERROR = "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0430\u043f\u043a\u0443 \u0432\u043d\u0443\u0442\u0440\u0438 Foundry Data."


def open_folder(deps: dict, form) -> bool:
    folder_key = form.get("folder", "")
    target = deps["allowed_open_folder"](folder_key)
    if target is None:
        return False
    target.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer.exe", str(target.resolve())])
    return True


def settings_page_context(deps: dict) -> dict:
    current_settings = deps["load_settings"]()
    return {
        "app_settings": current_settings,
        "foundry_data_display": Path(current_settings["foundry"]["data_dir"]).name or "Foundry Data",
        "foundry_links": deps["foundry_link_statuses"](current_settings),
        "app_update": deps["update_status"](),
    }


def check_for_updates(deps: dict) -> dict:
    return deps["check_for_updates"]()


def download_update(deps: dict) -> dict:
    return deps["download_update"]()


def install_update(deps: dict) -> dict:
    return deps["install_update"]()


def update_foundry_settings(deps: dict, form) -> None:
    current_settings = deps["load_settings"]()
    current_foundry = current_settings["foundry"]
    data_dir = Path(current_foundry["data_dir"])
    data_capability = form.get("foundry_data_capability", "").strip()
    if data_capability:
        data_dir = deps["resolve_directory_capability"](data_capability)
    try:
        assets_dir = normalize_relative_path(
            form.get("foundry_assets_dir", "").strip()
            or current_foundry["assets_dir"]
            or deps["DEFAULT_FOUNDRY_ASSETS_DIR"]
        )
        if data_dir.exists():
            resolve_destination_under(data_dir, assets_dir)
    except (OSError, PathBoundaryError) as exc:
        raise ValidationError("Foundry assets must be a relative path inside Foundry Data.") from exc
    current_settings["foundry"] = {
        "enabled": form.get("foundry_enabled") == "on",
        "data_dir": str(data_dir),
        "assets_dir": assets_dir,
    }
    deps["save_settings"](current_settings)


def update_spotlight_settings(deps: dict, form) -> None:
    current_settings = deps["load_settings"]()
    selected_materials = form.getlist("spotlight_materials")
    selected_campaigns = form.getlist("spotlight_campaigns")
    campaign_mode = form.get("spotlight_campaign_mode", "all")
    available_campaigns = {campaign.get("slug", "") for campaign in deps["get_campaigns"]()}
    current_settings["spotlight"] = {
        "materials": [option for option in deps["SPOTLIGHT_MATERIAL_OPTIONS"] if option in selected_materials]
        or deps["SPOTLIGHT_MATERIAL_OPTIONS"][:],
        "campaigns": [slug for slug in selected_campaigns if slug in available_campaigns],
        "campaign_mode": "selected" if campaign_mode == "selected" else "all",
    }
    deps["save_settings"](current_settings)


def update_demo_settings(deps: dict, form) -> None:
    current_settings = deps["load_settings"]()
    current_settings["demo"] = {
        "enabled": form.get("demo_enabled") == "on",
    }
    deps["save_settings"](current_settings)


def update_notification_settings(deps: dict, form) -> None:
    current_settings = deps["load_settings"]()
    current_settings["notifications"] = {
        "session_reminders_enabled": form.get("session_reminders_enabled") == "on",
        "session_reminder_days": form.get("session_reminder_days", "").strip(),
        "session_reminder_interval_hours": form.get("session_reminder_interval_hours", "").strip(),
    }
    deps["save_settings"](current_settings)


def update_appearance_settings(deps: dict, form) -> None:
    current_settings = deps["load_settings"]()
    selected_theme = form.get("appearance_theme", "").strip()
    current_settings["appearance"] = {
        "theme": selected_theme if selected_theme in THEME_OPTIONS else "madness-crown",
    }
    deps["save_settings"](current_settings)


def update_favorite_campaign_settings(deps: dict, form) -> None:
    selected_slug = form.get("campaign_slug", "").strip()
    available_campaigns = {campaign.get("slug", "") for campaign in deps["get_campaigns"]()}
    current_settings = deps["load_settings"]()
    favorites = current_settings.get("favorites", {})
    if not isinstance(favorites, dict):
        favorites = {}
    favorites["campaign_slug"] = selected_slug if selected_slug in available_campaigns else ""
    current_settings["favorites"] = favorites
    deps["save_settings"](current_settings)


def sync_foundry_links(deps: dict) -> tuple[list[dict], dict]:
    current_settings = deps["load_settings"]()
    before_rows = deps["foundry_link_statuses"](current_settings)
    rows = deps["ensure_foundry_junctions"](current_settings)
    return rows, deps["foundry_sync_summary"](rows, before_rows)


def pick_foundry_folder(deps: dict, form) -> tuple[dict, int]:
    field = form.get("field", "")
    if field not in {"data_dir", "assets_dir"}:
        return {"ok": False, "error": "invalid_picker_field"}, 422
    current_foundry = deps["load_settings"]()["foundry"]
    data_dir = Path(current_foundry["data_dir"])
    initial_path = data_dir if field == "data_dir" else data_dir / current_foundry["assets_dir"]
    title = FOUNDRY_DATA_TITLE if field == "data_dir" else FOUNDRY_ASSETS_TITLE
    try:
        selected = deps["choose_windows_folder"](str(initial_path), title)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return {"ok": False, "error": "picker_failed"}, 503
    if not selected:
        return {"ok": True, "cancelled": True}, 200

    if field == "data_dir":
        capability_id, display_name = deps["issue_directory_capability"](selected)
        return {
            "ok": True,
            "capability_id": capability_id,
            "display_name": display_name,
        }, 200

    try:
        selected_path = Path(selected).resolve(strict=True)
        root = data_dir.resolve(strict=True)
        value = normalize_relative_path(str(selected_path.relative_to(root)))
    except (OSError, ValueError, PathBoundaryError):
        return {"ok": False, "error": "assets_outside_foundry_data"}, 422
    if not selected_path.is_dir():
        return {"ok": False, "error": "selected_path_not_directory"}, 422
    try:
        resolve_destination_under(root, value)
    except (OSError, PathBoundaryError):
        return {"ok": False, "error": "assets_outside_foundry_data"}, 422
    return {
        "ok": True,
        "value": value,
        "display_name": selected_path.name,
    }, 200
