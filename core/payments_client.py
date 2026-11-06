"""Desktop-side client for the payment server. The desktop app can only START
a payment and READ its status. It never marks anything as paid."""
from __future__ import annotations

import subprocess
import sys
import time

import requests

from . import config

_server_proc: subprocess.Popen | None = None


def server_alive(timeout: float = 1.5) -> bool:
    try:
        return requests.get(f"{config.PAYMENT_SERVER_URL}/health", timeout=timeout).ok
    except requests.RequestException:
        return False


def ensure_server_running() -> bool:
    """Start the local payment server for demos if it isn't already running."""
    global _server_proc
    if server_alive():
        return True
    if config.PAYMENT_SERVER_HOST not in ("127.0.0.1", "localhost"):
        return False
    cmd = [sys.executable, "--payment-server"] if config.FROZEN else [sys.executable, "-m", "payment_server.server"]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console window on Windows
    _server_proc = subprocess.Popen(cmd, cwd=str(config.APP_DIR if config.FROZEN else config.ROOT),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    for _ in range(30):
        time.sleep(0.25)
        if server_alive(0.5):
            return True
    return False


def stop_server() -> None:
    if _server_proc and _server_proc.poll() is None:
        _server_proc.terminate()


def start(payment_id: int) -> dict:
    r = requests.post(f"{config.PAYMENT_SERVER_URL}/api/payments/{payment_id}/start", timeout=25)
    data = r.json()
    if not r.ok:
        raise RuntimeError(data.get("error", "Payment server error"))
    return data


def status(payment_id: int) -> dict:
    r = requests.get(f"{config.PAYMENT_SERVER_URL}/api/payments/{payment_id}", timeout=5)
    r.raise_for_status()
    return r.json()


def demo_mode() -> bool:
    try:
        return bool(requests.get(f"{config.PAYMENT_SERVER_URL}/health", timeout=2).json().get("demo_mode"))
    except requests.RequestException:
        return config.payments_in_demo_mode()
