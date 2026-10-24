"""Paths and single-instance ownership for source and frozen launches."""
import sys
from pathlib import Path


def default_data_dir() -> Path:
    if sys.platform == "win32":
        from .windows import local_app_data
        return local_app_data() / "ValTool Stream Overlay"
    return Path(__file__).resolve().parents[1] / ".data"


def default_frontend_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend" / "dist"
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def app_icon() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "app-icon.png"
    return Path(__file__).resolve().parents[2] / "packaging" / "app-icon.png"


class InstanceLock:
    def __init__(self, directory: Path):
        self.directory = directory
        self.file = None

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.file = (self.directory / ".instance.lock").open("a+b")
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b"\0")
            self.file.flush()
        self.file.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise OSError("The app is already running with this data directory. Close it before relaunching.") from None
        return self

    def __exit__(self, *args):
        # Closing the handle releases ownership even after an unexpected exit.
        self.file.close()


def startup_error(message: str):
    text = f"Could not start the app: {message}"
    if sys.stderr is not None:
        print(text, file=sys.stderr)
    else:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "ValTool Stream Overlay", 0x10)
