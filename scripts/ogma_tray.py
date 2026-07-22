from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from PIL import Image
import pystray


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
APP_FILE = PROJECT_ROOT / "app.py"
ICON_FILE = PROJECT_ROOT / "static" / "img" / "ogma-icon.png"
DATA_DIR = Path(os.getenv("OGMA_DATA_DIR", PROJECT_ROOT / "data")).resolve()
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "launcher.log"
SERVER_LOG_FILE = LOG_DIR / "server-console.log"
APP_HOST = "oghma.local"
BIND_HOST = "127.0.0.1"
APP_PORT = int(os.getenv("OGMA_PORT", "5000"))
APP_URL = f"http://{APP_HOST}"
HEALTH_URL = f"http://{BIND_HOST}:{APP_PORT}/health"
IPC_HOST = "127.0.0.1"
IPC_PORT = 51234
READY_TIMEOUT_SECONDS = 45

server_process: subprocess.Popen[str] | None = None
server_owned = False
server_ready = threading.Event()
server_failed = threading.Event()
shutdown_requested = threading.Event()
ipc_server_socket: socket.socket | None = None
icon_instance: pystray.Icon | None = None


def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ogma.launcher")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


LOGGER = configure_logging()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Oghma production tray launcher")
    parser.add_argument(
        "--startup",
        action="store_true",
        help="Start silently during Windows sign-in.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the browser after the server becomes ready.",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the running tray instance and its owned production server.",
    )
    return parser.parse_args()


def probe_server(timeout: float = 0.75) -> bool:
    request = urllib.request.Request(
        HEALTH_URL,
        headers={"Accept": "application/json", "Host": APP_HOST},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read(4096).decode("utf-8"))
    except (
        OSError,
        ValueError,
        urllib.error.URLError,
        urllib.error.HTTPError,
    ):
        return False
    return (
        payload.get("ok") is True
        and payload.get("service") == "ogma"
        and payload.get("status") == "ready"
    )


def notify(title: str, message: str) -> None:
    icon = icon_instance
    if icon is None:
        return
    try:
        icon.notify(message, title)
    except Exception:
        LOGGER.exception("Tray notification failed")


def open_app(_icon=None, _item=None) -> None:
    if probe_server():
        webbrowser.open(APP_URL, new=2)
        return
    notify(
        "Архив Огмы",
        "Сервер ещё запускается. Повторите через несколько секунд.",
    )


def open_launcher_log(_icon=None, _item=None) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch(exist_ok=True)
    subprocess.Popen(["notepad.exe", str(LOG_FILE)])


def open_server_log(_icon=None, _item=None) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    SERVER_LOG_FILE.touch(exist_ok=True)
    subprocess.Popen(["notepad.exe", str(SERVER_LOG_FILE)])


def wait_until_ready(process: subprocess.Popen[str]) -> bool:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline and not shutdown_requested.is_set():
        if process.poll() is not None:
            LOGGER.error(
                "Production server exited early with code %s",
                process.returncode,
            )
            return False
        if probe_server():
            return True
        time.sleep(0.25)
    LOGGER.error(
        "Production server readiness timed out after %s seconds",
        READY_TIMEOUT_SECONDS,
    )
    return False


def supervise_server(open_when_ready: bool) -> None:
    global server_process, server_owned

    if probe_server():
        LOGGER.info("Attached to an already running Oghma server at %s", APP_URL)
        server_ready.set()
        if open_when_ready:
            webbrowser.open(APP_URL, new=2)
        return

    env = os.environ.copy()
    env.update(
        {
            "OGMA_DEV": "0",
            "OGMA_HOST": BIND_HOST,
            "OGMA_PORT": str(APP_PORT),
            "PYTHONUNBUFFERED": "1",
        }
    )
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with SERVER_LOG_FILE.open("a", encoding="utf-8", buffering=1) as server_log:
        server_log.write("\n=== OGHMA PROD START ===\n")
        server_process = subprocess.Popen(
            [str(PYTHON_EXE), str(APP_FILE)],
            cwd=str(PROJECT_ROOT),
            stdout=server_log,
            stderr=server_log,
            text=True,
            env=env,
            creationflags=creationflags,
        )
        server_owned = True
        LOGGER.info("Started production server process pid=%s", server_process.pid)

        if not wait_until_ready(server_process):
            server_failed.set()
            notify(
                "Архив Огмы: ошибка запуска",
                "Сервер не запустился. Откройте журнал сервера из меню.",
            )
        else:
            server_ready.set()
            LOGGER.info("Production server is ready at %s", APP_URL)
            notify("Архив Огмы", "Production-сервер готов.")
            if open_when_ready:
                webbrowser.open(APP_URL, new=2)

        exit_code = server_process.wait()
        if not shutdown_requested.is_set() and exit_code != 0:
            server_failed.set()
            LOGGER.error(
                "Production server stopped unexpectedly with code %s",
                exit_code,
            )
            notify(
                "Архив Огмы: сервер остановлен",
                "Откройте журнал сервера для диагностики.",
            )
        else:
            LOGGER.info("Production server exited with code %s", exit_code)
        server_process = None
        server_owned = False


def send_to_existing_instance(command: bytes) -> bool:
    try:
        with socket.create_connection((IPC_HOST, IPC_PORT), timeout=0.75) as sock:
            sock.sendall(command + b"\n")
        return True
    except OSError:
        return False


def listen_commands() -> None:
    assert ipc_server_socket is not None
    while not shutdown_requested.is_set():
        try:
            connection, _address = ipc_server_socket.accept()
        except OSError:
            break
        with connection:
            try:
                command = connection.recv(128).strip().upper()
            except OSError:
                command = b""
        if command == b"OPEN":
            open_app()
        elif command == b"STOP" and icon_instance is not None:
            shutdown(icon_instance)


def stop_owned_server() -> None:
    process = server_process
    if not server_owned or process is None or process.poll() is not None:
        return
    LOGGER.info("Stopping owned production server pid=%s", process.pid)
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=4)


def shutdown(icon: pystray.Icon, _item=None) -> None:
    global ipc_server_socket
    shutdown_requested.set()
    stop_owned_server()
    if ipc_server_socket is not None:
        try:
            ipc_server_socket.close()
        except OSError:
            pass
        ipc_server_socket = None
    icon.stop()


def load_icon() -> Image.Image:
    if ICON_FILE.exists():
        with Image.open(ICON_FILE) as source:
            return source.convert("RGBA").copy()
    return Image.new("RGBA", (64, 64), (50, 90, 130, 255))


def main() -> int:
    global icon_instance, ipc_server_socket

    args = parse_args()
    if args.stop:
        return 0 if send_to_existing_instance(b"STOP") else 1
    open_when_ready = args.open and not args.startup
    command = b"OPEN" if open_when_ready else b"WAKE"
    if send_to_existing_instance(command):
        return 0

    if not PYTHON_EXE.is_file():
        LOGGER.error("Virtual environment Python not found: %s", PYTHON_EXE)
        return 1
    if not APP_FILE.is_file():
        LOGGER.error("Application entry point not found: %s", APP_FILE)
        return 1

    ipc_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        ipc_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ipc_server_socket.bind((IPC_HOST, IPC_PORT))
        ipc_server_socket.listen(5)
    except OSError:
        if send_to_existing_instance(command):
            return 0
        LOGGER.exception("Unable to acquire tray single-instance socket")
        return 1

    icon_instance = pystray.Icon(
        "ogma-tray",
        load_icon(),
        "Архив Огмы — PROD",
        menu=pystray.Menu(
            pystray.MenuItem("Открыть Архив Огмы", open_app, default=True),
            pystray.MenuItem("Журнал запуска", open_launcher_log),
            pystray.MenuItem("Журнал сервера", open_server_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход и остановка PROD", shutdown),
        ),
    )

    threading.Thread(target=listen_commands, daemon=True).start()
    threading.Thread(
        target=supervise_server,
        args=(open_when_ready,),
        daemon=True,
    ).start()
    icon_instance.run()
    return 1 if server_failed.is_set() else 0


if __name__ == "__main__":
    raise SystemExit(main())
