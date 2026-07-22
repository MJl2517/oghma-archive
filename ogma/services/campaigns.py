import subprocess


def index_context(deps: dict) -> dict:
    return {
        "campaigns": deps["get_campaigns"](),
        "shared_folders": deps["SHARED_FOLDERS"],
        "campaign_folders": deps["CAMPAIGN_FOLDERS"],
    }


def create_campaign(deps: dict, form) -> tuple[str, dict]:
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    system = form.get("system", "").strip()
    if not name:
        return "redirect_index", {}

    campaign = deps["create_campaign"](name, description, system)
    if deps["load_settings"]()["foundry"]["enabled"]:
        deps["ensure_foundry_junctions"]()
    return "redirect_campaign", campaign


def update_campaign(deps: dict, form, files, slug: str) -> tuple[str, dict]:
    if deps["get_campaign"](slug) is None:
        return "not_found", {}

    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    system = form.get("system", "").strip()
    remove_cover = form.get("remove_cover") == "1"
    cover_image = deps["save_campaign_cover"](slug, files.get("cover_image"))
    if not name:
        return "redirect_campaign", {"slug": slug}

    campaign = deps["update_campaign"](slug, name, description, system)
    if campaign is None:
        return "not_found", {}
    if remove_cover:
        deps["delete_campaign_cover"](slug)
        deps["set_campaign_cover"](slug, "")
    elif cover_image:
        deps["set_campaign_cover"](slug, cover_image)
    return "redirect_campaign", {"slug": slug}


def campaign_detail_context(deps: dict, slug: str) -> tuple[str, dict]:
    campaign = deps["get_campaign"](slug)
    if campaign is None:
        return "not_found", {}
    return "render", {
        "campaign": campaign,
        "campaign_folders": deps["CAMPAIGN_FOLDERS"],
        "nav_sections": deps["CAMPAIGN_SECTIONS"],
    }


def open_campaign_folder(deps: dict, slug: str) -> str:
    if deps["get_campaign"](slug) is None:
        return "not_found"
    target = deps["CAMPAIGNS_DIR"] / slug
    target.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer.exe", str(target.resolve())])
    return "ok"


def open_campaign_section_folder(deps: dict, slug: str, folder: str) -> str:
    if deps["get_campaign"](slug) is None or folder not in deps["CAMPAIGN_FOLDERS"]:
        return "not_found"
    target = deps["CAMPAIGNS_DIR"] / slug / folder
    target.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer.exe", str(target.resolve())])
    return "ok"


def delete_campaign(deps: dict, slug: str) -> str:
    if deps["get_campaign"](slug) is None:
        return "not_found"
    return "disabled"


def campaign_cover_directory(deps: dict, campaign_slug: str):
    if deps["get_campaign"](campaign_slug) is None:
        return None
    return deps["campaign_cover_directory"](campaign_slug)
