"""Exercise an already-built Windows bundle with isolated data and no browser."""
import argparse
import json
import re
import subprocess
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def tray_registered(pid):
    """Ask the Windows shell whether this process has a registered tray icon."""
    class Identifier(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('hWnd', wintypes.HWND), ('uID', wintypes.UINT), ('guidItem', ctypes.c_byte * 16)]
    user = ctypes.WinDLL('user32', use_last_error=True)
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    shell.Shell_NotifyIconGetRect.argtypes = [ctypes.POINTER(Identifier), ctypes.POINTER(wintypes.RECT)]
    shell.Shell_NotifyIconGetRect.restype = ctypes.c_long
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, unused):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            name = ctypes.create_unicode_buffer(256)
            user.GetClassNameW(hwnd, name, len(name))
            match = re.fullmatch(r'valtool-stream-overlay(\d+)SystemTrayIcon', name.value)
            if match:
                # pystray 0.19.5 registers the default uID (0), scoped to its HWND.
                identifier = Identifier(cbSize=ctypes.sizeof(Identifier), hWnd=hwnd, uID=0)
                rectangle = wintypes.RECT()
                if shell.Shell_NotifyIconGetRect(ctypes.byref(identifier), ctypes.byref(rectangle)) == 0:
                    found.append(True)
        return True
    user.EnumWindows.argtypes = [type(callback), wintypes.LPARAM]
    user.EnumWindows(callback, 0)
    return bool(found)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--expected-version", help="Require this version in the packaged health and editor responses")
    parser.add_argument("--tray", action="store_true", help="Verify the actual Windows tray icon (requires an interactive desktop)")
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    directory = root / "work" / ("smoke-live" if options.live else "smoke-demo") / "Ścieżka with spaces"
    directory.mkdir(parents=True, exist_ok=True)
    bootstrap = directory / "editor-bootstrap.txt"
    origin = "http://127.0.0.1:32155"
    key = None
    with httpx.Client(base_url=origin, trust_env=False, timeout=10, headers={"Origin": origin}) as client:
        for _ in range(2):
            bootstrap.unlink(missing_ok=True)
            command = [str(options.executable.resolve()), "--no-browser", "--port", "32155", "--data-dir", str(directory),
                       "--editor-url-file", str(bootstrap)]
            if not options.tray:
                command.append('--no-tray')
            if not options.live:
                command.append("--demo")
            process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic() + 30
                while not bootstrap.exists():
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Packaged server did not start")
                    time.sleep(.1)
                secret = urlsplit(bootstrap.read_text()).fragment.split("=", 1)[1]
                assert client.post("/api/session", headers={"Authorization": "Bearer " + secret}).status_code == 204
                health = client.get("/api/health")
                assert health.status_code == 200
                if options.expected_version:
                    assert health.json()['version'] == options.expected_version
                if options.tray:
                    deadline = time.monotonic() + 10
                    while not tray_registered(process.pid) and time.monotonic() < deadline:
                        time.sleep(.1)
                    assert tray_registered(process.pid), 'The Windows shell did not register the tray icon'
                editor = client.get("/api/editor").json()
                if options.expected_version:
                    assert editor['version'] == options.expected_version
                if key:
                    assert editor["overlayUrl"] == key
                key = editor["overlayUrl"]
                html = client.get("/settings").text
                for asset in re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"', html):
                    assert client.get(asset).status_code == 200
                assert client.get("/ranks/19.png").status_code == 200
                assert client.get("/agents/add6443a-41bd-e414-f6ad-e58d267f4e95.png").status_code == 200
                overlay = key.replace("/overlay/", "/api/overlay/")
                with client.stream("GET", overlay + "/events") as stream:
                    assert stream.status_code == 200
                    assert next(line for line in stream.iter_lines() if line.startswith("data: "))
                if options.live:
                    deadline = time.monotonic() + 150
                    while time.monotonic() < deadline:
                        snapshot = client.get(overlay).json()
                        if snapshot["rank"] is not None and snapshot['loaded'] > 0 and not snapshot["syncing"]:
                            break
                        time.sleep(.5)
                    assert snapshot["connection"]["authenticated"] and snapshot["rank"] is not None
                    assert snapshot['loaded'] > 0 and snapshot['stats']['games'] > 0
                    assert snapshot['syncError'] in (None, 'Waiting for final details of some matches.')
                    assert snapshot["mode"] == "live"
                    print(json.dumps({"live": True, "loaded": snapshot["loaded"], "syncError": snapshot["syncError"]}))
                else:
                    assert client.get(overlay).json()["mode"] == "demo"
                assert client.post("/api/shutdown").status_code == 202
                assert process.wait(timeout=15) == 0
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                client.cookies.clear()
    print("Packaged startup, authentication, assets, SSE, shutdown, restart and stable OBS URL: passed")
    if options.tray:
        print('Windows shell tray registration: passed')


if __name__ == "__main__":
    main()
