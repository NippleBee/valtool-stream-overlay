import argparse
import asyncio
import sys
import webbrowser
from pathlib import Path

import uvicorn

from .app import create_app
from .runtime import InstanceLock, app_icon, default_data_dir, startup_error


async def serve(options):
    server = None
    app = create_app(options.data_dir, port=options.port, demo=options.demo, dev_ui=options.dev_ui,
                     frontend_dir=options.frontend_dir, lockfile=options.lockfile,
                     on_shutdown=lambda: setattr(server, "should_exit", True))
    config = uvicorn.Config(app, host="127.0.0.1", port=app.state.storage.configuration.port,
                            access_log=False, log_level="warning", timeout_graceful_shutdown=3,
                            **({"log_config": None} if sys.stderr is None else {}))
    server = uvicorn.Server(config)
    async def run_server():
        try:
            await server.serve()
        except SystemExit as error:
            raise OSError("Port unavailable. Check whether another instance is already running.") from error

    task = asyncio.create_task(run_server())
    while not server.started and not task.done():
        await asyncio.sleep(0.02)
    if not server.started:
        await task
        return
    tray = None
    def open_editor():
        # A fresh one-time URL is needed every time settings are reopened.
        webbrowser.open(app.state.security.new_editor_url())

    url = app.state.security.new_editor_url()
    if sys.stdout is not None:
        print(f"ValTool Stream Overlay · {app.state.security.base_url}", flush=True)
    if options.editor_url_file:
        options.editor_url_file.parent.mkdir(parents=True, exist_ok=True)
        options.editor_url_file.write_text(url)
        options.editor_url_file.chmod(0o600)
    try:
        if sys.platform == "win32" and not options.no_tray:
            from .tray import SystemTray
            tray = SystemTray(app_icon(), open_editor, app.state.worker.request_refresh,
                              lambda: setattr(server, "should_exit", True))
            await tray.start()
        if not options.no_browser:
            open_editor()
        await task
    finally:
        server.should_exit = True
        if tray is not None:
            await tray.stop()
        if not task.done():
            await task


def main():
    parser = argparse.ArgumentParser(description="ValTool Stream Overlay")
    parser.add_argument("--demo", action="store_true", help="Use sample data for the whole server, including OBS")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--port", type=int, choices=range(1024, 65536), metavar="PORT")
    parser.add_argument("--frontend-dir", type=Path)
    parser.add_argument("--lockfile", type=Path, help="Override automatic Windows Riot Client lockfile discovery")
    parser.add_argument("--dev-ui", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-tray", action="store_true", help="Disable the Windows tray icon for automation")
    parser.add_argument("--editor-url-file", type=Path, help="Write a short-lived bootstrap URL for local automation")
    options = parser.parse_args()
    try:
        options.data_dir = options.data_dir or default_data_dir()
        with InstanceLock(options.data_dir):
            asyncio.run(serve(options))
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as error:
        startup_error(str(error))
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
