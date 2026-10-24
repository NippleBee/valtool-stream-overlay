import asyncio
import json
import secrets
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from . import __version__
from .models import Settings
from .riot import Catalog, FileSessionProvider, RiotClient
from .security import LocalSecurity
from .service import OverlayService, RiotWorker
from .storage import Storage


def create_app(data_dir: Path, *, port: int | None = None, demo: bool = False, dev_ui: bool = False,
               frontend_dir: Path | None = None, lockfile: Path | None = None,
               worker: RiotWorker | None = None, on_shutdown=None) -> FastAPI:
    storage = Storage(data_dir, port)
    security = LocalSecurity(storage.configuration.port, dev_ui)
    service = OverlayService(storage, demo)
    if worker is None:
        catalog = Catalog()
        provider = FileSessionProvider(lockfile, catalog) if lockfile else None
        worker = RiotWorker(service, RiotClient(), provider, catalog)
    else:
        worker.service = service
    settings_lock = asyncio.Lock()
    stopping = asyncio.Event()
    frontend = (frontend_dir or Path(__file__).resolve().parents[2] / "frontend" / "dist").resolve()

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(worker.run())
        try:
            yield
        finally:
            stopping.set()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await worker.client.close()

    app = FastAPI(title="ValTool Stream Overlay", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.storage, app.state.service, app.state.security = storage, service, security
    app.state.worker, app.state.stopping = worker, stopping

    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        # Do not reflect submitted input (or arbitrary exception context) back to the browser.
        return JSONResponse({"error": "Invalid settings or request parameters."}, status_code=400)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if not security.valid_request(request):
            return Response(status_code=403)
        path = request.url.path
        public = path in {"/api/health", "/api/session"} or path.startswith("/api/overlay/")
        if path.startswith("/api/") and not public and not security.is_editor(request):
            return Response(status_code=401)
        response = await call_next(request)
        response.headers.update({
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; object-src 'none'",
        })
        return response

    @app.get("/api/health")
    async def health():
        return {"application": "valtool-stream-overlay", "version": __version__}

    @app.post("/api/session")
    async def session(request: Request):
        if not security.bootstrap(request.headers.get("authorization", "")):
            return Response(status_code=401)
        response = Response(status_code=204)
        response.set_cookie(security.cookie_name, security._session, httponly=True, samesite="strict", path="/api", max_age=86400)
        return response

    @app.get("/api/editor")
    async def editor():
        return {"overlayUrl": f"{security.base_url}/overlay/{storage.configuration.overlay_key}",
                "snapshot": service.snapshot().json_data(), "version": __version__}

    @app.get("/api/matches")
    async def matches():
        return [match.json_data() for match in service.all_matches()]

    @app.put("/api/settings")
    async def settings(settings: Settings):
        async with settings_lock:
            selection_changed = (settings.match_count, settings.scope) != (service.settings.match_count, service.settings.scope)
            try:
                await service.update_settings(settings)
            except OSError:
                return JSONResponse({"error": "Could not save settings to disk."}, status_code=500)
            worker.request_refresh(selection_changed)
            return service.snapshot().json_data()

    @app.post("/api/refresh", status_code=202)
    async def refresh():
        worker.request_refresh()
        return None

    @app.post("/api/shutdown", status_code=202)
    async def shutdown():
        stopping.set()
        if on_shutdown:
            on_shutdown()
        return None

    def check_key(key: str):
        if not secrets.compare_digest(key.encode(), storage.configuration.overlay_key.encode()):
            raise HTTPException(status_code=404)

    @app.get("/api/overlay/{key}")
    async def overlay(key: str, preview: str | None = None):
        check_key(key)
        return service.snapshot(preview == "demo").json_data()

    @app.get("/api/overlay/{key}/events")
    async def events(key: str, request: Request, preview: str | None = None):
        check_key(key)

        async def stream():
            queue = service.subscribe()
            stop_task = asyncio.create_task(stopping.wait())
            read_task = None
            try:
                while not stopping.is_set():
                    read_task = asyncio.create_task(queue.get())
                    done, _ = await asyncio.wait({read_task, stop_task}, timeout=15, return_when=asyncio.FIRST_COMPLETED)
                    if stop_task in done or await request.is_disconnected():
                        break
                    if read_task in done:
                        snapshot = service.snapshot(preview == "demo")
                        yield f"id: {snapshot.revision}\ndata: {json.dumps(snapshot.json_data(), separators=(',', ':'), ensure_ascii=False)}\n\n"
                    else:
                        yield ": heartbeat\n\n"
                    if not read_task.done():
                        read_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await read_task
            finally:
                for task in (read_task, stop_task):
                    if task and not task.done():
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task
                service.unsubscribe(queue)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.api_route("/{path:path}", methods=["GET", "HEAD"])
    async def static(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        asset = (frontend / path).resolve()
        if not asset.is_relative_to(frontend):
            raise HTTPException(status_code=404)
        if asset.is_file():
            return FileResponse(asset)
        if path in {"", "settings"} or path.startswith("overlay/"):
            index = frontend / "index.html"
            if index.is_file():
                return FileResponse(index)
            return Response("Frontend build missing. Run npm run build.", status_code=503)
        raise HTTPException(status_code=404)

    return app
