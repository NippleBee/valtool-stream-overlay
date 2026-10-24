"""Windows discovery using documented OS APIs; no game memory access."""

import asyncio
import ctypes
import re
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path

from .riot import Catalog, FileSessionProvider, LocalRiotClient, Lockfile


def local_app_data() -> Path:
    # CSIDL_LOCAL_APPDATA resolves the real user folder even in a redirected shell.
    buffer = ctypes.create_unicode_buffer(32768)
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.SHGetFolderPathW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR]
    shell.SHGetFolderPathW.restype = ctypes.c_long
    if shell.SHGetFolderPathW(None, 0x001C, None, 0, buffer) != 0:
        raise OSError("Could not locate the Windows local application data directory")
    return Path(buffer.value)


def processes() -> dict[int, str]:
    """Return PID/executable names without opening the processes themselves."""
    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    for name in ("Process32FirstW", "Process32NextW"):
        function = getattr(kernel, name)
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        function.restype = wintypes.BOOL
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        result = {}
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            result[entry.th32ProcessID] = entry.szExeFile.lower()
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
        return result
    finally:
        kernel.CloseHandle(handle)


def installed_version(directory: Path) -> str | None:
    try:
        with (directory / "VALORANT/Saved/Logs/ShooterGame.log").open(encoding="utf-8", errors="replace") as log:
            header = log.read(262144)
    except OSError:
        return None
    values = [re.search(r"LogShooter: Display: " + pattern, header) for pattern in (
        r"Branch: (release-[\d.]+)", r"Build version: (\d+)", r"Changelist: (\d+)",
    )]
    if all(values):
        branch, build, changelist = (value[1] for value in values)
        return f"{branch}-shipping-{build}-{changelist}"
    return None


class WindowsSessionProvider:
    def __init__(self, catalog: Catalog, local: LocalRiotClient | None = None, *,
                 directory: Path | None = None, process_reader=processes):
        self.directory = directory if directory is not None else local_app_data()
        self.path = self.directory / "Riot Games/Riot Client/Config/lockfile"
        self.process_reader = process_reader
        # Recheck the local token endpoint on each monitor poll: account switches do
        # not necessarily replace the lockfile or restart RiotClientServices.
        self.provider = FileSessionProvider(self.path, catalog, local, cache_seconds=0)

    def invalidate(self):
        self.provider.invalidate()

    async def discover(self):
        current = await asyncio.to_thread(self.process_reader)
        try:
            lock = Lockfile.parse(await asyncio.to_thread(self.path.read_text, encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self.provider.reset()
            return None
        if current.get(lock.pid) != "riotclientservices.exe":
            self.provider.reset()
            return None
        self.provider.version_override = await asyncio.to_thread(installed_version, self.directory)
        session = await self.provider.discover()
        if session is None:
            return None
        running = "valorant-win64-shipping.exe" in current.values()
        return replace(session, running=running)
