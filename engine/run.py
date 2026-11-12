"""Start the engine and (by default) a free public HTTPS tunnel, then print a one-click link that
connects the website to it.   Usage:  python -m engine.run  [--no-tunnel] [--port 7860]"""
from __future__ import annotations

import argparse
import os
import platform
import re
import stat
import subprocess
import tarfile
import threading
import time
import urllib.parse
import urllib.request

import uvicorn

from . import media
from .config import BIN_DIR, SITE_URL, TOKEN

CLOUDFLARED = "https://github.com/cloudflare/cloudflared/releases/latest/download/"


def cloudflared_path() -> str:
    """Download the cloudflared binary for this OS once (no account needed for quick tunnels)."""
    system, arch = platform.system().lower(), platform.machine().lower()
    arch = "arm64" if arch in {"arm64", "aarch64"} else "amd64"
    exe = BIN_DIR / ("cloudflared.exe" if system == "windows" else "cloudflared")
    if exe.exists():
        return str(exe)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    if system == "darwin":
        tgz = BIN_DIR / "cloudflared.tgz"
        urllib.request.urlretrieve(f"{CLOUDFLARED}cloudflared-darwin-{arch}.tgz", tgz)
        with tarfile.open(tgz) as t:
            t.extractall(BIN_DIR)
    else:
        name = f"cloudflared-windows-{arch}.exe" if system == "windows" else f"cloudflared-linux-{arch}"
        urllib.request.urlretrieve(CLOUDFLARED + name, exe)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(exe)


def start_tunnel(port: int) -> str:
    proc = subprocess.Popen([cloudflared_path(), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + 90
    for line in proc.stdout:
        if m := re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line):
            threading.Thread(target=lambda: [None for _ in proc.stdout], daemon=True).start()  # keep draining
            return m.group(0)
        if time.time() > deadline:
            break
    raise RuntimeError("cloudflared did not return a public URL")


def connect_link(url: str) -> str:
    return f"{SITE_URL}#" + urllib.parse.urlencode({"engine": url, "token": TOKEN})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "7860")))
    ap.add_argument("--no-tunnel", action="store_true", help="local only (Chrome on this computer)")
    args = ap.parse_args()

    media.ensure_ffmpeg()
    server = uvicorn.Server(uvicorn.Config("engine.server:app", host="127.0.0.1", port=args.port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.2)

    url = f"http://127.0.0.1:{args.port}" if args.no_tunnel else start_tunnel(args.port)
    bar = "=" * 70
    print(f"\n{bar}\n  ✅ المحرك شغال: {url}\n\n  افتحي اللينك ده عشان الموقع يتوصل بالمحرك:\n\n  {connect_link(url)}\n"
          f"\n  (سيبي النافذة دي مفتوحة طول ما بتشتغلي. Ctrl+C للإيقاف)\n{bar}\n", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.should_exit = True


if __name__ == "__main__":
    main()
