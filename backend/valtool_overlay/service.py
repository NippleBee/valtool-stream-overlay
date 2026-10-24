import asyncio
from contextlib import suppress
from datetime import UTC, datetime

import httpx

from . import demo
from .models import Connection, Match, Rank, Settings, Snapshot
from .riot import Catalog, RiotClient, RiotError, Session, SessionProvider, WaitingProvider, parse_match
from .statistics import calculate
from .storage import Storage


class OverlayService:
    def __init__(self, storage: Storage, demo_mode: bool = False):
        self.storage = storage
        self.settings = storage.configuration.overlay
        self.demo_mode = demo_mode
        self.demo_matches = demo.matches()
        self.records: dict[str, Match] = {}
        self.rank: Rank | None = None
        self.connection = Connection()
        self.history_complete = False
        self.pending_details = False
        self.syncing = False
        self.total: int | None = None
        self.sync_error: str | None = None
        self.revision = 0
        self._subscribers: set[asyncio.Queue] = set()

    def snapshot(self, preview_demo: bool = False) -> Snapshot:
        is_demo = self.demo_mode or preview_demo
        rank = demo.RANK if is_demo else self.rank
        records = self.demo_matches if is_demo else list(self.records.values())
        stats, recent = calculate(records, self.settings, rank.season_id if rank else None, is_demo or self.history_complete)
        if not is_demo and self.pending_details:
            stats = stats.model_copy(update={"is_complete": False})
        connection = Connection(phase="demo", message="Sample data", account="VALTOOL#DEMO") if is_demo else self.connection
        return Snapshot(
            revision=self.revision, settings=self.settings, connection=connection, rank=rank, stats=stats,
            recent_matches=recent, mode="demo" if is_demo else "live", loaded=len(records),
            total=len(records) if is_demo else self.total, syncing=False if is_demo else self.syncing,
            sync_error=None if is_demo else self.sync_error,
        )

    def publish(self):
        self.revision += 1
        for queue in self._subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(self.revision)

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        queue.put_nowait(self.revision)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._subscribers.discard(queue)

    async def update_settings(self, settings: Settings):
        await asyncio.to_thread(self.storage.save_settings, settings)
        self.settings = settings
        self.publish()

    def set_connection(self, connection: Connection):
        if connection != self.connection:
            self.connection = connection
            self.publish()

    def clear_account(self):
        self.records, self.rank = {}, None
        self.total, self.sync_error = None, None
        self.syncing = self.history_complete = self.pending_details = False
        self.publish()

    def all_matches(self) -> list[Match]:
        return sorted(self.demo_matches if self.demo_mode else self.records.values(), key=lambda m: -m.started_at)


class RiotWorker:
    def __init__(self, service: OverlayService, client: RiotClient, provider: SessionProvider | None = None, catalog: Catalog | None = None):
        self.service, self.client = service, client
        self.catalog = catalog or Catalog()
        self.provider = provider or WaitingProvider()
        self.session: Session | None = None
        self._last_account: str | None = None
        self._sync_task: asyncio.Task | None = None
        self._wakeup = asyncio.Event()
        self._reauth = False

    def request_refresh(self, cancel_selection: bool = False):
        if cancel_selection and self._sync_task:
            self._sync_task.cancel()
        self._wakeup.set()

    async def run(self):
        if self.service.demo_mode:
            return
        async with asyncio.TaskGroup() as group:
            group.create_task(self._monitor())
            group.create_task(self._synchronize())

    async def _monitor(self):
        while True:
            try:
                session = await self.provider.discover()
                previous = self.session.cache_key if self.session else None
                next_key = session.cache_key if session else None
                if previous != next_key:
                    if self._sync_task:
                        self._sync_task.cancel()
                    if session and self._last_account != next_key:
                        self.service.clear_account()
                        self._last_account = next_key
                    self._wakeup.set()
                self.session = session
                if session:
                    connection = self.service.connection.model_copy(update={
                        "phase": "connected", "message": "VALORANT connected" if session.running else "Riot Client connected",
                        "authenticated": True, "riot_client_available": True, "valorant_running": session.running, "error": None,
                    })
                    self.service.set_connection(connection)
                    if self._reauth:
                        self._reauth = False
                        self._wakeup.set()
                else:
                    self.service.set_connection(self.service.connection.model_copy(update={
                        "phase": "waiting", "message": "Waiting for Riot Client",
                        "authenticated": False, "riot_client_available": False, "valorant_running": False,
                    }))
            except (OSError, ValueError, httpx.HTTPError, RiotError):
                if self._sync_task:
                    self._sync_task.cancel()
                self.session = None
                self.service.set_connection(self.service.connection.model_copy(update={
                    "phase": "waiting", "authenticated": False,
                    "message": "Could not obtain a Riot session. Retrying automatically.",
                }))
            await asyncio.sleep(2)

    async def _synchronize(self):
        while True:
            try:
                await asyncio.wait_for(self._wakeup.wait(), timeout=30)
            except TimeoutError:
                pass
            self._wakeup.clear()
            if self.session is None:
                continue
            session = self.session
            self._sync_task = asyncio.create_task(self.sync(session))
            try:
                await self._sync_task
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
                self.service.syncing = False
                self.service.publish()
            except (httpx.HTTPError, RiotError, ValueError, KeyError):
                # Only an actual authentication error triggers a refresh, not every 403.
                error = self._sync_task.exception()
                if isinstance(error, RiotError) and error.authentication_failure:
                    self.provider.invalidate()
                    self._reauth = True
                self.service.syncing = False
                self.service.sync_error = "Refresh is temporarily unavailable. Keeping the latest data."
                self.service.publish()
            finally:
                self._sync_task = None

    async def sync(self, session: Session):
        await self.catalog.load()
        rank = self.catalog.rank(await self.client.mmr(session))
        await asyncio.to_thread(self.service.storage.save_context, session.puuid, session.context())
        cached = {m.id: m for m in await asyncio.to_thread(self.service.storage.read_matches, session.cache_key)}
        self.service.rank, self.service.records = rank, cached
        self.service.syncing, self.service.history_complete = True, False
        self.service.sync_error = None
        self.service.publish()
        settings = self.service.settings
        target = max(settings.match_count or 0, settings.recent_count)

        ratings: dict[str, int] = {}
        cursor = 0
        while True:
            response = await self.client.updates(session, cursor)
            page = response.get("Matches", [])
            before = len(ratings)
            for update in page:
                if type(update.get("RankedRatingEarned")) is int:
                    ratings[update["MatchID"]] = update["RankedRatingEarned"]
            if len(page) < 20 or len(ratings) == before:
                break
            if settings.match_count is not None and settings.scope == "available" and len(ratings) >= target:
                break
            if settings.scope == "act" and rank.season_id and all(u.get("SeasonID") != rank.season_id for u in page):
                break
            cursor += 20
        for mid, record in list(cached.items()):
            if mid in ratings and record.rating_delta != ratings[mid]:
                cached[mid] = record.model_copy(update={"rating_delta": ratings[mid]})
                await asyncio.to_thread(self.service.storage.save_match, session.cache_key, cached[mid])

        visited: set[str] = set()
        pending = False
        cursor = 0
        while True:
            page = await self.client.history(session, cursor)
            items = page.get("History", [])
            self.service.total = page.get("Total")

            async def fetch(item):
                mid = item["MatchID"]
                if mid in cached and cached[mid].is_final and cached[mid].outcome != "unknown":
                    return cached[mid]
                return parse_match(await self.client.details(session, mid), session.puuid, ratings.get(mid), self.catalog)

            for index in range(0, len(items), 2):
                records = await asyncio.gather(*(fetch(item) for item in items[index:index + 2]))
                for record in records:
                    if record is None or record.outcome == "unknown":
                        pending = True
                        continue
                    visited.add(record.id)
                    cached[record.id] = record
                    await asyncio.to_thread(self.service.storage.save_match, session.cache_key, record)
                self.service.pending_details = pending
                self.service.publish()
            end, total = page.get("EndIndex", cursor), page.get("Total", 0)
            if not items or end >= total:
                self.service.history_complete = not pending
                break
            if end <= cursor:
                self.service.sync_error = "History pagination did not advance. Retrying later."
                break
            count = sum(mid in visited and not m.is_remake and m.outcome != "unknown"
                        and (settings.scope != "act" or m.season_id == rank.season_id) for mid, m in cached.items())
            if settings.match_count is not None and count >= target:
                break
            cursor = end
        self.service.pending_details = pending
        self.service.syncing = False
        if pending:
            self.service.sync_error = "Waiting for final details of some matches."
        self.service.set_connection(self.service.connection.model_copy(update={"updated_at": datetime.now(UTC), "error": None}))
        self.service.publish()
