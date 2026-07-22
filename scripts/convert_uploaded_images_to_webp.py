from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import DATA_DIR, storage
from ogma.media import ALLOWED_IMAGE_EXTENSIONS, save_image_as_webp


SOURCE_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS - {".webp"}
SKIPPED_DIR_NAMES = {".cache", "__pycache__"}


def is_skipped(path: Path) -> bool:
    return any(part in SKIPPED_DIR_NAMES for part in path.parts)


def unique_webp_path(source: Path) -> Path:
    target = source.with_suffix(".webp")
    if not target.exists():
        return target
    counter = 2
    while True:
        candidate = source.with_name(f"{source.stem}-{counter}.webp")
        if not candidate.exists():
            return candidate
        counter += 1


def convert_existing_images(dry_run: bool = False) -> tuple[dict[str, str], list[tuple[Path, str]], int, int, int]:
    replacements: dict[str, str] = {}
    failures: list[tuple[Path, str]] = []
    total_before = 0
    total_after = 0
    converted = 0

    for source in sorted(DATA_DIR.rglob("*")):
        if not source.is_file() or is_skipped(source):
            continue
        if source.suffix.lower() not in SOURCE_EXTENSIONS:
            continue

        target = unique_webp_path(source)
        try:
            before = source.stat().st_size
            if not dry_run:
                save_image_as_webp(source, target)
                source.unlink()
            after = target.stat().st_size if target.exists() else 0
        except Exception as exc:
            target.unlink(missing_ok=True)
            failures.append((source, str(exc)))
            continue

        old_relative = source.relative_to(DATA_DIR).as_posix()
        new_relative = target.relative_to(DATA_DIR).as_posix()
        replacements[source.name] = target.name
        replacements[old_relative] = new_relative
        replacements[str(source.relative_to(DATA_DIR))] = str(target.relative_to(DATA_DIR))
        for parent in source.parents:
            if parent == DATA_DIR:
                break
            replacements[source.relative_to(parent).as_posix()] = target.relative_to(parent).as_posix()
        total_before += before
        total_after += after
        converted += 1

    return replacements, failures, total_before, total_after, converted


def replace_metadata_value(value, replacements: dict[str, str]):
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        if value in replacements:
            return replacements[value]
        if normalized in replacements:
            return replacements[normalized]
        return value
    if isinstance(value, list):
        return [replace_metadata_value(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: replace_metadata_value(item, replacements) for key, item in value.items()}
    return value


def save_if_changed(loader, saver, replacements: dict[str, str]) -> int:
    items = loader()
    updated = replace_metadata_value(items, replacements)
    if updated == items:
        return 0
    saver(updated)
    return 1


def update_metadata(replacements: dict[str, str], dry_run: bool = False) -> int:
    if not replacements or dry_run:
        return 0

    changed = 0
    campaigns = storage.load_campaigns()
    updated_campaigns = replace_metadata_value(campaigns, replacements)
    for campaign in updated_campaigns:
        if isinstance(campaign, dict):
            campaign.pop("cover_url", None)
    if updated_campaigns != campaigns:
        storage.save_campaigns(updated_campaigns)
        changed += 1

    campaign_slugs = [str(item.get("slug", "")).strip() for item in updated_campaigns if str(item.get("slug", "")).strip()]

    changed += save_if_changed(
        lambda: storage.load_maps("shared"),
        lambda items: storage.save_maps("shared", items),
        replacements,
    )
    changed += save_if_changed(storage.load_scenes, storage.save_scenes, replacements)
    changed += save_if_changed(storage.load_audio_tracks, storage.save_audio_tracks, replacements)
    changed += save_if_changed(storage.load_resources, storage.save_resources, replacements)
    changed += save_if_changed(lambda: storage.load_rules() or [], storage.save_rules, replacements)
    changed += save_if_changed(storage.load_generators, storage.save_generators, replacements)

    for slug in campaign_slugs:
        changed += save_if_changed(
            lambda slug=slug: storage.load_maps("campaign", slug),
            lambda items, slug=slug: storage.save_maps("campaign", items, slug),
            replacements,
        )
        changed += save_if_changed(
            lambda slug=slug: storage.load_characters(slug),
            lambda items, slug=slug: storage.save_characters(slug, items),
            replacements,
        )
        changed += save_if_changed(
            lambda slug=slug: storage.load_notes(slug),
            lambda items, slug=slug: storage.save_notes(slug, items),
            replacements,
        )
        changed += save_if_changed(
            lambda slug=slug: storage.load_gods(slug),
            lambda items, slug=slug: storage.save_gods(slug, items),
            replacements,
        )

    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert uploaded Oghma images in data/ to WebP.")
    parser.add_argument("--dry-run", action="store_true", help="Scan files without writing changes.")
    args = parser.parse_args()

    replacements, failures, total_before, total_after, converted = convert_existing_images(dry_run=args.dry_run)
    changed_metadata = update_metadata(replacements, dry_run=args.dry_run)

    print(f"converted={converted}")
    print(f"metadata_collections_updated={changed_metadata}")
    print(f"total_before={total_before}")
    print(f"total_after={total_after}")
    if total_before and total_after:
        print(f"ratio={total_after / total_before:.3f}")
    if failures:
        print(f"failures={len(failures)}")
        for path, error in failures[:20]:
            print(f"{path}: {error}")


if __name__ == "__main__":
    main()
