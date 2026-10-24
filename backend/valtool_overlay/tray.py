"""Windows tray lifecycle. All app actions run on the asyncio event loop."""
import asyncio
import threading
from pathlib import Path


class SystemTray:
    def __init__(self, image_path: Path, open_editor, refresh, quit_app):
        import pystray
        from PIL import Image

        self.loop = asyncio.get_running_loop()
        self.ready = threading.Event()
        self.error = None
        self.thread = None
        self.image = Image.open(image_path).convert("RGBA")

        def action(callback):
            def invoke(icon, item):
                self.loop.call_soon_threadsafe(callback)
            return invoke

        self.icon = pystray.Icon("valtool-stream-overlay", self.image, "ValTool Stream Overlay", pystray.Menu(
            pystray.MenuItem("Open ValTool Stream Overlay", action(open_editor), default=True),
            pystray.MenuItem("Refresh match statistics", action(refresh)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit ValTool Stream Overlay", action(quit_app)),
        ))

    async def start(self):
        def setup(icon):
            try:
                icon.visible = True
            except Exception as error:
                self.error = error
            finally:
                self.ready.set()

        def run():
            try:
                self.icon.run(setup=setup)
            except Exception as error:
                self.error = error
                self.ready.set()

        self.thread = threading.Thread(target=run, name="ValTool tray", daemon=True)
        self.thread.start()
        ready = await asyncio.to_thread(self.ready.wait, 5)
        if not ready or self.error is not None:
            await self.stop()
            raise OSError("Could not create the Windows tray icon. Restart the app or launch with --no-tray.") from None

    async def stop(self):
        await asyncio.to_thread(self.icon.stop)
        if self.thread is not None:
            await asyncio.to_thread(self.thread.join, 5)
        self.image.close()
