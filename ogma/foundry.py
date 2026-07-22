import base64
import subprocess
from pathlib import Path

from ogma.safe_paths import normalize_relative_path


def normalize_foundry_relative_path(*parts: str) -> str:
    cleaned = []
    for part in parts:
        value = str(part or "").replace("\\", "/").strip("/")
        if value:
            cleaned.append(value)
    return normalize_relative_path("/".join(cleaned))


def junction_status(link_path: Path, target_path: Path) -> dict:
    exists = link_path.exists()
    if not exists:
        return {"state": "missing", "ok": False, "message": "\u0421\u0441\u044b\u043b\u043a\u0430 \u0435\u0449\u0451 \u043d\u0435 \u0441\u043e\u0437\u0434\u0430\u043d\u0430."}
    try:
        if link_path.resolve() == target_path.resolve():
            return {"state": "linked", "ok": True, "message": "\u0421\u0441\u044b\u043b\u043a\u0430 \u0430\u043a\u0442\u0438\u0432\u043d\u0430."}
    except OSError:
        pass
    return {
        "state": "conflict",
        "ok": False,
        "message": "\u041f\u043e \u044d\u0442\u043e\u043c\u0443 \u043f\u0443\u0442\u0438 \u0443\u0436\u0435 \u0435\u0441\u0442\u044c \u043f\u0430\u043f\u043a\u0430 \u0438\u043b\u0438 \u0441\u0441\u044b\u043b\u043a\u0430 \u043d\u0430 \u0434\u0440\u0443\u0433\u043e\u0435 \u043c\u0435\u0441\u0442\u043e.",
    }


def remove_junction(link_path: Path, target_path: Path | None = None) -> bool:
    if not link_path.exists():
        return False
    try:
        if target_path is not None and link_path.resolve() != target_path.resolve():
            return False
    except OSError:
        if target_path is not None:
            return False

    escaped_link = str(link_path).replace("'", "''")
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$item = Get-Item -LiteralPath '{escaped_link}' -Force\n"
        "if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) { exit 3 }\n"
        f"Remove-Item -LiteralPath '{escaped_link}' -Force\n"
    )
    encoded_command = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-EncodedCommand", encoded_command],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    return True


def create_junction(link_path: Path, target_path: Path) -> dict:
    target_path.mkdir(parents=True, exist_ok=True)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    status = junction_status(link_path, target_path)
    if status["state"] == "linked":
        return status
    if status["state"] == "conflict":
        return status

    escaped_link = str(link_path).replace("'", "''")
    escaped_target = str(target_path).replace("'", "''")
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"New-Item -ItemType Junction -Path '{escaped_link}' -Target '{escaped_target}' | Out-Null\n"
    )
    encoded_command = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-EncodedCommand", encoded_command],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return junction_status(link_path, target_path)


def link_statuses(specs: list[dict]) -> list[dict]:
    rows = []
    for spec in specs:
        status = junction_status(spec["link"], spec["target"])
        rows.append({**spec, **status})
    return rows


def ensure_junctions(specs: list[dict]) -> list[dict]:
    rows = []
    for spec in specs:
        try:
            status = create_junction(spec["link"], spec["target"])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            status = {
                "state": "error",
                "ok": False,
                "message": "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0437\u0434\u0430\u0442\u044c junction-\u0441\u0441\u044b\u043b\u043a\u0443.",
            }
        rows.append({**spec, **status})
    return rows


def sync_summary(rows: list[dict], before_rows: list[dict] | None = None) -> dict:
    linked_count = sum(1 for row in rows if row.get("state") == "linked")
    problem_count = len(rows) - linked_count
    before_problem_count = None
    if before_rows is not None:
        before_problem_count = sum(1 for row in before_rows if row.get("state") != "linked")

    if problem_count:
        message = f"\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u043e: \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u0441\u0441\u044b\u043b\u043e\u043a {linked_count}, \u0442\u0440\u0435\u0431\u0443\u044e\u0442 \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u044f {problem_count}."
        state = "warning"
    elif before_problem_count:
        message = f"\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u043e: {linked_count} \u0441\u0441\u044b\u043b\u043e\u043a Foundry \u0430\u043a\u0442\u0438\u0432\u043d\u044b."
        state = "success"
    else:
        message = f"\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043d\u0435 \u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f: {linked_count} \u0441\u0441\u044b\u043b\u043e\u043a Foundry \u0443\u0436\u0435 \u0430\u043a\u0442\u0438\u0432\u043d\u044b."
        state = "success"
    return {"linked": linked_count, "problems": problem_count, "message": message, "state": state}
