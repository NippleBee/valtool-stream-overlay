import asyncio
import sys
import threading
from types import SimpleNamespace

import pytest

from valtool_overlay.runtime import app_icon
from valtool_overlay.tray import SystemTray


@pytest.mark.asyncio
async def test_tray_dispatches_menu_actions_to_app_loop_and_releases_thread(monkeypatch):
    class Item:
        def __init__(self, text, callback, **kwargs):
            self.text, self.callback = text, callback
    class Menu:
        SEPARATOR = object()
        def __init__(self, *items):
            self.items = items
    class Icon:
        def __init__(self, name, image, title, menu):
            self.menu = menu
            self.visible = False
            self.stopped = threading.Event()
        def run(self, setup):
            setup(self)
            self.stopped.wait(5)
        def stop(self):
            self.visible = False
            self.stopped.set()
    class Image:
        def convert(self, mode): return self
        def close(self): pass
    monkeypatch.setitem(sys.modules, 'pystray', SimpleNamespace(Icon=Icon, Menu=Menu, MenuItem=Item))
    monkeypatch.setitem(sys.modules, 'PIL', SimpleNamespace(Image=SimpleNamespace(open=lambda path: Image())))
    events = []
    main_thread = threading.get_ident()
    tray = SystemTray(app_icon(), lambda: events.append(('open', threading.get_ident())),
                      lambda: events.append(('refresh', threading.get_ident())),
                      lambda: events.append(('quit', threading.get_ident())))
    await tray.start()
    try:
        assert tray.icon.visible
        assert [item.text for item in tray.icon.menu.items if isinstance(item, Item)] == [
            'Open ValTool Stream Overlay', 'Refresh match statistics', 'Quit ValTool Stream Overlay']
        for index in (0, 1, 3):
            item = tray.icon.menu.items[index]
            await asyncio.to_thread(item.callback, tray.icon, item)
        await asyncio.sleep(0)
        assert events == [(name, main_thread) for name in ('open', 'refresh', 'quit')]
    finally:
        await tray.stop()
    assert not tray.icon.visible and not tray.thread.is_alive()
