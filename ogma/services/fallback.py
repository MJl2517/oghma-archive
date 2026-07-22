def section_target(deps: dict, slug: str, selected_campaign: str) -> tuple[str, dict]:
    current_section = deps["get_section"](slug)
    if current_section is None:
        return "not_found", {}

    campaign = deps["get_campaign"](selected_campaign) if selected_campaign else None
    if slug in {"maps", "scenes", "audio", "resources", "rules"}:
        return "redirect_endpoint", {"endpoint": f"{slug}_page", "values": {}}
    if slug == "characters":
        if campaign:
            return "redirect_endpoint", {"endpoint": "characters_page", "values": {"campaign": selected_campaign}}
        return "redirect_endpoint", {"endpoint": "index", "values": {}}
    if slug == "party":
        if campaign:
            return "redirect_endpoint", {"endpoint": "party_page", "values": {"campaign": selected_campaign}}
        return "redirect_endpoint", {"endpoint": "index", "values": {}}
    if slug == "notes":
        if campaign:
            return "redirect_endpoint", {"endpoint": "notes_page", "values": {"campaign": selected_campaign}}
        return "redirect_endpoint", {"endpoint": "index", "values": {}}

    if current_section.get("campaign_only") and campaign is None:
        return "redirect_endpoint", {"endpoint": "index", "values": {}}
    if not current_section.get("campaign_only"):
        campaign = None
    return "render_section", {"section": current_section, "campaign": campaign}
