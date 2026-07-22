from __future__ import annotations

import importlib
import gc
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DATA_DIR = ROOT / "data"
THIS_FILE = Path(__file__).resolve()
RU_BANDIT = "\u0411\u0430\u043d\u0434\u0438\u0442"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class Check:
    name: str
    ok: bool
    details: str = ""


def _clear_json_readonly(data_dir: Path) -> dict[str, int]:
    changed = 0
    failed = 0
    for path in data_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IWUSR)
            changed += 1
        except OSError:
            failed += 1
    return {"changed": changed, "failed": failed}


@contextmanager
def _data_sandbox():
    old_data_dir = os.environ.get("OGMA_DATA_DIR")
    with tempfile.TemporaryDirectory(prefix="ogma-step6-", ignore_cleanup_errors=True) as temp_dir:
        sandbox_data_dir = Path(temp_dir) / "data"
        shutil.copytree(
            SOURCE_DATA_DIR,
            sandbox_data_dir,
            ignore=shutil.ignore_patterns(".cache"),
        )
        readonly_stats = _clear_json_readonly(sandbox_data_dir)
        os.environ["OGMA_DATA_DIR"] = str(sandbox_data_dir)
        try:
            yield sandbox_data_dir, readonly_stats
        finally:
            gc.collect()
            if old_data_dir is None:
                os.environ.pop("OGMA_DATA_DIR", None)
            else:
                os.environ["OGMA_DATA_DIR"] = old_data_dir


def _restore_latest_metadata_backup(data_dir: Path) -> bool:
    backups_dir = ROOT / "backups"
    candidates = sorted(backups_dir.glob("sqlite-migration-*"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        return False
    backup_dir = candidates[0]
    for path in backup_dir.rglob("*.json"):
        relative = path.relative_to(backup_dir)
        target = data_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return True


def _load_app(backend: str):
    os.environ["STORAGE_BACKEND"] = backend
    if "app" in sys.modules:
        app_module = importlib.reload(sys.modules["app"])
    else:
        app_module = importlib.import_module("app")
    return app_module


def _latest_by_title(items: list[dict], title: str) -> dict | None:
    for item in reversed(items):
        if str(item.get("title", "")) == title:
            return item
    return None


def _png_file(name: str = "test.png"):
    # Minimal valid PNG bytes.
    png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\xd9\x9f\x1b"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return io.BytesIO(png), name


def run_crud_and_search() -> dict[str, Any]:
    with _data_sandbox() as (data_dir, readonly_stats):
        app_module = _load_app("sqlite")
        client = app_module.app.test_client()
        checks: list[Check] = []
        prefix = f"step6-{int(time.time())}"
        # Campaign CRUD
        campaign_name = f"{prefix}-campaign"
        r = client.post("/campaigns", data={"name": campaign_name, "description": "step6", "system": "5e"})
        checks.append(Check("campaign_create", r.status_code in {302, 303}, f"status={r.status_code}"))
        campaign_slug = ""
        for payload in app_module.storage.load_campaigns():
            if str(payload.get("name", "")) == campaign_name:
                campaign_slug = str(payload.get("slug", ""))
                break
        checks.append(Check("campaign_visible", bool(campaign_slug), campaign_slug))

        if campaign_slug:
            r = client.post(f"/campaigns/{campaign_slug}/update", data={"name": campaign_name + "-u", "description": "upd", "system": "5e"})
            checks.append(Check("campaign_update", r.status_code in {302, 303}, f"status={r.status_code}"))

        # Rules CRUD
        rule_title = f"{prefix}-rule"
        r = client.post("/rules/add", data={"title": rule_title, "tag": "Step6", "source": "XGE", "content": "step6 body"})
        checks.append(Check("rules_create", r.status_code in {302, 303}, f"status={r.status_code}"))
        rule = _latest_by_title(app_module.load_rules(), rule_title)
        rule_id = rule.get("id", "") if rule else ""
        checks.append(Check("rules_visible", bool(rule_id), rule_id))
        if rule_id:
            r = client.post(f"/rules/{rule_id}/update", data={"title": rule_title + "-u", "tag": "Step6", "source": "XGE", "content": "updated"})
            checks.append(Check("rules_update", r.status_code in {200, 302, 303}, f"status={r.status_code}"))

        # Resources CRUD
        resource_title = f"{prefix}-resource"
        r = client.post("/resources/create", data={"source_type": "web", "url": "https://example.com", "title": resource_title, "description": "step6", "category": "РџСЂРѕС‡РµРµ", "tags": "step6"})
        checks.append(Check("resources_create", r.status_code in {302, 303}, f"status={r.status_code}"))
        resource = _latest_by_title(app_module.load_resources(), resource_title)
        resource_id = resource.get("id", "") if resource else ""
        checks.append(Check("resources_visible", bool(resource_id), resource_id))
        if resource_id:
            r = client.post(f"/resources/{resource_id}/update", data={"source_type": "web", "url": "https://example.com/u", "title": resource_title + "-u", "description": "upd", "category": "РџСЂРѕС‡РµРµ", "tags": "step6"})
            checks.append(Check("resources_update", r.status_code in {302, 303}, f"status={r.status_code}"))

        # Audio CRUD (link)
        audio_title = f"{prefix}-audio"
        r = client.post("/audio/create-link", data={"title": audio_title, "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "category": "РњСѓР·С‹РєР°", "tags": "step6"})
        checks.append(Check("audio_create_link", r.status_code in {302, 303}, f"status={r.status_code}"))
        audio_track = _latest_by_title(app_module.load_audio_tracks(), audio_title)
        track_id = audio_track.get("id", "") if audio_track else ""
        checks.append(Check("audio_visible", bool(track_id), track_id))
        if track_id:
            r = client.post(f"/audio/{track_id}/update", data={"title": audio_title + "-u", "category": "РњСѓР·С‹РєР°", "tags": "step6", "source_type": "youtube", "source": "https://youtu.be/dQw4w9WgXcQ"})
            checks.append(Check("audio_update", r.status_code in {200, 302, 303}, f"status={r.status_code}"))

        # Maps upload/update/delete
        map_title = f"{prefix}-map"
        map_file, map_name = _png_file("map.png")
        r = client.post("/maps/upload", data={"scope": "shared", "batch_tags": "step6", "single_title": map_title, "maps": (map_file, map_name)}, content_type="multipart/form-data")
        checks.append(Check("maps_upload", r.status_code in {302, 303}, f"status={r.status_code}"))
        maps = app_module.load_maps("shared")
        map_item = _latest_by_title(maps, map_title)
        map_id = map_item.get("id", "") if map_item else ""
        checks.append(Check("maps_visible", bool(map_id), map_id))
        if map_id:
            r = client.post(f"/maps/{map_id}/update", data={"scope": "shared", "title": map_title + "-u", "tags": "step6"}, headers={"X-Requested-With": "fetch", "Accept": "application/json"})
            checks.append(Check("maps_update", r.status_code == 200, f"status={r.status_code}"))

        # Scenes upload/update/delete
        scene_title = f"{prefix}-scene"
        scene_file, scene_name = _png_file("scene.png")
        r = client.post("/scenes/upload", data={"batch_tags": "step6", "single_title": scene_title, "scenes": (scene_file, scene_name)}, content_type="multipart/form-data")
        checks.append(Check("scenes_upload", r.status_code in {302, 303}, f"status={r.status_code}"))
        scenes = app_module.load_scenes()
        scene_item = _latest_by_title(scenes, scene_title)
        scene_id = scene_item.get("id", "") if scene_item else ""
        checks.append(Check("scenes_visible", bool(scene_id), scene_id))
        if scene_id:
            r = client.post(f"/scenes/{scene_id}/update", data={"title": scene_title + "-u", "tags": "step6"}, headers={"X-Requested-With": "fetch", "Accept": "application/json"})
            checks.append(Check("scenes_update", r.status_code == 200, f"status={r.status_code}"))

        # Characters + Notes inside created campaign
        character_id = ""
        note_id = ""
        if campaign_slug:
            char_title = f"{prefix}-npc"
            char_file, char_name = _png_file("npc.png")
            r = client.post(
            "/characters/upload",
            data={"campaign_slug": campaign_slug, "single_title": char_title, "batch_tags": "NPC,step6", "characters": (char_file, char_name)},
            content_type="multipart/form-data",
        )
            checks.append(Check("characters_upload", r.status_code in {302, 303}, f"status={r.status_code}"))
            chars = app_module.load_characters(campaign_slug)
            char = next((c for c in reversed(chars) if str(c.get("name", "")) == char_title), None)
            character_id = char.get("id", "") if char else ""
            checks.append(Check("characters_visible", bool(character_id), character_id))
            if character_id:
                r = client.post(
                    f"/characters/{character_id}/update",
                    data={"campaign_slug": campaign_slug, "name": char_title + "-u", "tags": "NPC,step6", "race": "", "attitude": "РќРµР№С‚СЂР°Р»СЊРЅС‹Р№", "notes": "step6 bio"},
                    headers={"X-Requested-With": "fetch", "Accept": "application/json"},
                )
                checks.append(Check("characters_update", r.status_code == 200, f"status={r.status_code}"))

            note_title = f"{prefix}-note {RU_BANDIT} bandit"
            r = client.post(
                "/notes/create",
                data={
                    "campaign_slug": campaign_slug,
                    "title": note_title,
                    "planned_body": f"{RU_BANDIT} step6",
                    "happened_body": "РџСЂРѕРёР·РѕС€Р»Рѕ РІ Р­Р»Р»РёР±",
                    "status": "РџСЂРѕРІРµРґРµРЅР°",
                    "tags": "step6",
                    "world_date": "2026-05-07",
                    "references_json": "[]",
                },
                headers={"X-Requested-With": "fetch", "Accept": "application/json"},
            )
            checks.append(Check("notes_create", r.status_code == 200, f"status={r.status_code}"))
            notes = app_module.load_notes(campaign_slug)
            note = _latest_by_title(app_module.prepare_notes(campaign_slug), note_title)
            note_id = note.get("id", "") if note else ""
            checks.append(Check("notes_visible", bool(note_id), note_id))
            if note_id:
                r = client.post(
                    f"/notes/{note_id}/update",
                    data={
                        "campaign_slug": campaign_slug,
                        "title": note_title + "-u",
                        "planned_body": "updated plan",
                        "happened_body": "updated happened",
                        "status": "РџСЂРѕРІРµРґРµРЅР°",
                        "tags": "step6",
                        "world_date": "2026-05-07",
                        "references_json": "[]",
                    },
                    headers={"X-Requested-With": "fetch", "Accept": "application/json"},
                )
                checks.append(Check("notes_update", r.status_code == 200, f"status={r.status_code}"))

        # Search scenarios
        queries = [
            ("bandit", True),
            (RU_BANDIT, True),
            ("step6", True),
            ("npc", True),
            ("XGE", True),
            ("music", True),
        ]
        for q, should_have in queries:
            r = client.get(f"/spotlight/search?q={q}")
            ok = r.status_code == 200
            items = (r.get_json() or {}).get("items", []) if ok else []
            if should_have:
                ok = ok and len(items) > 0
            checks.append(Check(f"search_{q}", ok, f"status={r.status_code}, items={len(items)}"))

        # Cleanup
        if rule_id:
            client.post(f"/rules/{rule_id}/delete", headers={"X-Requested-With": "fetch", "Accept": "application/json"})
        if resource_id:
            client.post("/resources/delete", data={"resource_ids": [resource_id]})
        if track_id:
            client.post("/audio/delete", data={"track_ids": [track_id]})
        if map_id:
            client.post("/maps/delete", data={"scope": "shared", "map_ids": [map_id]})
        if scene_id:
            client.post("/scenes/delete", data={"scene_ids": [scene_id]})
        if campaign_slug and character_id:
            client.post("/characters/delete", data={"campaign_slug": campaign_slug, "character_ids": [character_id]})
        if campaign_slug and note_id:
            client.post("/notes/delete", data={"campaign_slug": campaign_slug, "note_ids": [note_id]})
        if campaign_slug:
            client.post(f"/campaigns/{campaign_slug}/delete")

        passed = sum(1 for c in checks if c.ok)
        return {
            "checks": [c.__dict__ for c in checks],
            "passed": passed,
            "total": len(checks),
            "readonly_unset": readonly_stats,
        }


def _benchmark_backend(backend: str, loops: int = 30) -> dict[str, Any]:
    with _data_sandbox() as (data_dir, _readonly_stats):
        restored_json_baseline = False
        if backend == "json":
            restored_json_baseline = _restore_latest_metadata_backup(data_dir)
        app_module = _load_app(backend)
        client = app_module.app.test_client()
        routes = ["/", "/maps", "/scenes", "/audio", "/resources", "/rules", "/spotlight/search?q=РіРѕСЂРѕРґ"]
        durations = []
        statuses = {}
        for _ in range(loops):
            for route in routes:
                start = time.perf_counter()
                r = client.get(route)
                statuses[route] = r.status_code
                durations.append(time.perf_counter() - start)
        durations.sort()
        p50 = durations[int(len(durations) * 0.50)]
        p95 = durations[int(len(durations) * 0.95)]
        avg = sum(durations) / len(durations)
        ok_statuses = all(status < 500 for status in statuses.values())
        return {
            "backend": backend,
            "samples": len(durations),
            "avg_ms": avg * 1000,
            "p50_ms": p50 * 1000,
            "p95_ms": p95 * 1000,
            "statuses": statuses,
            "ok_statuses": ok_statuses,
            "restored_json_baseline": restored_json_baseline,
        }


def run_benchmark_compare() -> dict[str, Any]:
    cmd_base = [sys.executable, str(THIS_FILE), "--bench-backend"]
    json_run = subprocess.check_output(cmd_base + ["json"], cwd=ROOT, text=True)
    sqlite_run = subprocess.check_output(cmd_base + ["sqlite"], cwd=ROOT, text=True)
    json_stats = json.loads(json_run)
    sqlite_stats = json.loads(sqlite_run)
    faster = sqlite_stats["avg_ms"] < json_stats["avg_ms"]
    faster_p95 = sqlite_stats["p95_ms"] < json_stats["p95_ms"]
    return {"json": json_stats, "sqlite": sqlite_stats, "sqlite_faster_avg": faster, "sqlite_faster_p95": faster_p95}


def run_migration_checks() -> dict[str, Any]:
    app_module = _load_app("sqlite")
    metadata_json = [
        str(path.relative_to(ROOT / "data"))
        for path in (ROOT / "data").rglob("*.json")
        if path.name != "settings.json"
    ]
    counts = app_module.storage.sqlite.table_counts()
    latest_backup = None
    backups = sorted((ROOT / "backups").glob("sqlite-migration-*"), key=lambda path: path.stat().st_mtime, reverse=True)
    if backups:
        latest_backup = str(backups[0].relative_to(ROOT))
    return {
        "settings_json_exists": (ROOT / "data" / "settings.json").exists(),
        "metadata_json_remaining": metadata_json,
        "metadata_json_absent": not metadata_json,
        "latest_backup": latest_backup,
        "table_counts": counts,
        "legacy_payload_tables_empty": counts.get("metadata_lists") == 0 and counts.get("label_lists") == 0,
    }


def run_migration_checks_subprocess() -> dict[str, Any]:
    output = subprocess.check_output([sys.executable, str(THIS_FILE), "--migration-check"], cwd=ROOT, text=True)
    return json.loads(output)


def main() -> None:
    if "--bench-backend" in sys.argv:
        backend = sys.argv[sys.argv.index("--bench-backend") + 1]
        print(json.dumps(_benchmark_backend(backend), ensure_ascii=False))
        return
    if "--migration-check" in sys.argv:
        print(json.dumps(run_migration_checks(), ensure_ascii=False))
        return

    report = {
        "crud_and_search": run_crud_and_search(),
        "migration": run_migration_checks_subprocess(),
        "benchmark": run_benchmark_compare(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
