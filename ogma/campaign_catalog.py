import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ogma.json_store import read_json, write_json
from ogma.media import save_uploaded_media_file


class CampaignCatalog:
    def __init__(
        self,
        campaigns_dir: Path,
        campaign_folders: list[str],
        campaign_metadata_path,
        campaign_cover_directory,
        allowed_image_extensions: set[str],
    ) -> None:
        self.campaigns_dir = campaigns_dir
        self.campaign_folders = campaign_folders
        self.campaign_metadata_path = campaign_metadata_path
        self.campaign_cover_directory = campaign_cover_directory
        self.allowed_image_extensions = allowed_image_extensions

    def slugify(self, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "-", name.strip().lower(), flags=re.UNICODE)
        slug = slug.strip("-")
        return slug or f"campaign-{uuid4().hex[:8]}"

    def list(self, cover_url_builder=None) -> list[dict]:
        campaigns = []
        for path in sorted(self.campaigns_dir.glob("*/campaign.json")):
            metadata = read_json(path)
            slug = path.parent.name
            metadata["slug"] = slug
            metadata.setdefault("foundry_slug", slug)
            if metadata.get("cover_image") and cover_url_builder is not None:
                metadata["cover_url"] = cover_url_builder(slug, metadata["cover_image"])
            campaigns.append(metadata)
        return sorted(campaigns, key=lambda item: item.get("created_at", ""), reverse=True)

    def foundry_slug(self, campaign_or_slug: dict | str | None) -> str:
        if isinstance(campaign_or_slug, dict):
            return (
                str(campaign_or_slug.get("foundry_slug") or campaign_or_slug.get("slug") or "").strip()
                or self.slugify(campaign_or_slug.get("name", ""))
            )
        return str(campaign_or_slug or "").strip()

    def get(self, slug: str, cover_url_builder=None) -> dict | None:
        metadata_path = self.campaign_metadata_path(slug)
        if not metadata_path.exists():
            return None

        campaign = read_json(metadata_path)
        campaign["slug"] = slug
        campaign.setdefault("foundry_slug", slug)
        if campaign.get("cover_image") and cover_url_builder is not None:
            campaign["cover_url"] = cover_url_builder(slug, campaign["cover_image"])
        return campaign

    def create(self, name: str, description: str = "", system: str = "") -> dict:
        base_slug = self.slugify(name)
        slug = base_slug
        counter = 2

        while (self.campaigns_dir / slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        campaign_dir = self.campaigns_dir / slug
        campaign_dir.mkdir(parents=True, exist_ok=False)
        for folder in self.campaign_folders:
            (campaign_dir / folder).mkdir(exist_ok=True)

        now = datetime.now().isoformat(timespec="seconds")
        campaign = {
            "slug": slug,
            "foundry_slug": slug,
            "name": name.strip(),
            "description": description.strip(),
            "system": system.strip(),
            "created_at": now,
            "updated_at": now,
            "folders": self.campaign_folders,
        }
        write_json(self.campaign_metadata_path(slug), campaign)
        return campaign

    def update(self, slug: str, name: str, description: str = "", system: str = "") -> dict | None:
        campaign = self.get(slug)
        if campaign is None:
            return None

        campaign["name"] = name.strip() or campaign.get("name", slug)
        campaign["description"] = description.strip()
        campaign["system"] = system.strip()
        campaign["foundry_slug"] = self.foundry_slug(campaign) or slug
        campaign["updated_at"] = datetime.now().isoformat(timespec="seconds")
        campaign.pop("slug", None)
        write_json(self.campaign_metadata_path(slug), campaign)
        campaign["slug"] = slug
        return campaign

    def save_cover(self, slug: str, uploaded_file) -> str | None:
        if not uploaded_file or not uploaded_file.filename:
            return None

        extension = Path(uploaded_file.filename).suffix.lower()
        if extension not in self.allowed_image_extensions:
            return None

        target_dir = self.campaign_cover_directory(slug)
        target_dir.mkdir(parents=True, exist_ok=True)
        for old_file in target_dir.iterdir():
            if old_file.is_file():
                old_file.unlink()

        saved_file = save_uploaded_media_file(uploaded_file, target_dir, self.allowed_image_extensions, "cover", suffix_length=10)
        return saved_file["filename"] if saved_file else None

    def delete_cover(self, slug: str) -> None:
        target_dir = self.campaign_cover_directory(slug)
        if not target_dir.exists():
            return
        for old_file in target_dir.iterdir():
            if old_file.is_file():
                old_file.unlink()
