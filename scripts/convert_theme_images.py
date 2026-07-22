from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "oghma_themes"
TARGET_ROOT = ROOT / "static" / "img" / "themes"
MAX_WIDTH = 2560
WEBP_QUALITY = 84


THEMES = {
    "Корона Безумия": (
        "madness-crown",
        {
            "Abandoned_royal_records": "records-hall",
            "Ancient_ruined_library": "ruined-library",
            "Collapsed_university": "collapsed-university",
            "Deep_archive_vault": "archive-vault",
            "Forgotten_archive": "forgotten-archive",
            "Forgotten_ritual_archive": "ritual-archive",
            "Labyrinth_of_ancient": "stone-stacks",
            "Moonlit_ruins": "occult-observatory",
            "Occult_study": "occult-study",
            "Old_wizard_laboratory": "wizard-lab",
            "Ruined_cathedral": "arcane-cathedral",
            "Underground_scriptorium": "scriptorium",
        },
    ),
    "Голод Хадара": (
        "hadar-hunger",
        {
            "Ancient_fortress": "starless-fortress",
            "Astral_sea": "astral-sea",
            "Astral_storm": "astral-storm",
            "Black_castle": "black-castle",
            "Broken_bridge": "broken-bridge",
            "Cosmic_cavern": "cosmic-cavern",
            "Lonely_chapel": "astral-chapel",
            "Night_sky": "void-rift",
            "Observatory_balcony": "void-observatory",
            "Rural_night_field": "alien-field",
            "Star-haunted": "star-haunted-field",
            "Violet-black": "astral-vacuum",
        },
    ),
    "Добряника": (
        "goodberry",
        {
            "Ancient_forest_ravine": "magical-ravine",
            "Ancient_tree_roots": "living-ruins",
            "Dense_magical_thicket": "magical-thicket",
            "Druidic_stone_circle": "druidic-circle",
            "Forest_spring": "forest-spring",
            "Living_wall_of_trees": "living-arch",
            "Moonlit_druid_grove": "moonlit-grove",
            "Overgrown_druid_sanctuary": "overgrown-sanctuary",
            "Rushing_forest_river": "rushing-river",
            "Untamed_woodland_shrine": "woodland-shrine",
            "Wild_druidic_grove": "wild-grove",
            "Wild_valley": "wild-valley",
        },
    ),
    "Луч холода": (
        "frost-ray",
        {
            "Abandoned_fortress": "frozen-fortress",
            "Ancient_blue_ice_cavern": "ice-cavern-plain",
            "Arctic_shoreline": "arctic-shore",
            "Castle_of_dark_stone": "icebound-castle",
            "Coast_of_a_freezing": "freezing-coast",
            "Frozen_waterfall": "frozen-waterfall",
            "Glacier_canyon": "glacier-canyon",
            "Ice_cave": "blue-ice-cave",
            "Moonlit_ice_desert": "moonlit-ice",
            "Snow_valley": "blizzard-valley",
            "Snowy_valley": "snowy-valley",
            "Vast_icy_mountain": "icy-mountains",
        },
    ),
    "Щит веры": (
        "shield-faith",
        {
            "Ancient_fortified_church": "fortified-church",
            "Cathedral_nave": "cathedral-nave",
            "Country_church": "country-church",
            "Golden_castle_courtyard": "golden-courtyard",
            "Golden_stone_castle": "golden-castle",
            "Grand_church_interior": "grand-church",
            "Hilltop_sanctuary": "hilltop-sanctuary",
            "Old_church_library": "church-library",
            "Pilgrim_road": "pilgrim-road",
            "Rolling_golden_fields": "golden-fields",
            "Sanctuary_hall": "oath-hall",
            "Sunlit_monastery": "sunlit-monastery",
        },
    ),
}


def output_name(source_name: str, mapping: dict[str, str]) -> str:
    for marker, name in mapping.items():
        if marker in source_name:
            return f"{name}.webp"
    raise ValueError(f"No output mapping for {source_name}")


def convert_image(source: Path, target: Path) -> tuple[int, int]:
    with Image.open(source) as image:
        image = image.convert("RGB")
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / image.width
            size = (MAX_WIDTH, round(image.height * ratio))
            image = image.resize(size, Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, "WEBP", quality=WEBP_QUALITY, method=6)
        return image.size


def main() -> None:
    total_before = 0
    total_after = 0
    converted = []

    for source_folder, (theme_slug, mapping) in THEMES.items():
        folder = SOURCE_ROOT / source_folder
        if not folder.exists():
            raise FileNotFoundError(f"Missing theme folder: {folder}")

        for source in sorted(folder.glob("*.png")):
            target = TARGET_ROOT / theme_slug / output_name(source.name, mapping)
            size = convert_image(source, target)
            total_before += source.stat().st_size
            total_after += target.stat().st_size
            converted.append((source_folder, source.name, target.relative_to(ROOT), size, source.stat().st_size, target.stat().st_size))

    for source_folder, source_name, target, size, before, after in converted:
        print(f"{source_folder}: {source_name} -> {target} {size[0]}x{size[1]} {before} -> {after}")

    print(f"converted={len(converted)}")
    print(f"total_before={total_before}")
    print(f"total_after={total_after}")
    if total_before:
        print(f"ratio={total_after / total_before:.3f}")


if __name__ == "__main__":
    main()
