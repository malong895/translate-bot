"""Single-instance supervisor so the translate bot stays up 24/7.

Run with:  venv\\Scripts\\pythonw.exe service_runner.py
It keeps exactly ONE bot.py process alive, restarting it if it crashes and
preventing duplicate instances (which cause Telegram getUpdates conflicts).
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
SERVICE_LOG = LOG_DIR / "service.log"
BOT_LOG = LOG_DIR / "bot.log"
MUTEX_NAME = "Local\\TranslateBot_Supervisor"
CREATE_NO_WINDOW = 0x08000000
ERROR_ALREADY_EXISTS = 183

_MUTEX_HANDLE = None


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with SERVICE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {message}\n")


def acquire_single_instance() -> bool:
    global _MUTEX_HANDLE
    if os.name != "nt":
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return False
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _MUTEX_HANDLE = handle
    return True


def run_bot_once() -> float:
    python = BASE_DIR / "venv" / "Scripts" / "python.exe"
    bot = BASE_DIR / "bot.py"
    if not python.exists() or not bot.exists():
        log("ERROR venv or bot.py missing")
        return 60.0

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with BOT_LOG.open("ab", buffering=0) as out:
        proc = subprocess.Popen(
            [str(python), "-u", str(bot)],
            cwd=str(BASE_DIR),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        log(f"bot started pid={proc.pid}")
        code = proc.wait()
    runtime = time.monotonic() - started
    log(f"bot exited code={code} after {runtime:.0f}s")
    return 30.0 if runtime < 30.0 else 5.0


def main() -> int:
    if not acquire_single_instance():
        log("another supervisor is already running - exiting")
        return 0
    log(f"supervisor started pid={os.getpid()}")
    while True:
        time.sleep(run_bot_once())


if __name__ == "__main__":
    raise SystemExit(main())
