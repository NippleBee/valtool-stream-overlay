"""OS-independent Riot transport. Windows process/lockfile discovery is a provider seam.

No real Riot connection is attempted unless a lockfile provider is explicitly configured.
Credentials never form part of the public snapshot or persistent storage.
"""

import asyncio
import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import quote
from uuid import UUID

import httpx

from .models import Match, Rank

SHARDS = {"na", "eu", "ap", "kr", "latam", "br", "pbe"}
PLATFORM = base64.b64encode(json.dumps({
    "platformType": "PC", "platformOS": "Windows",
    "platformOSVersion": "10.0.19045.1.256.64bit", "platformChipset": "Unknown",
}, separators=(",", ":")).encode()).decode()


@dataclass(frozen=True)
class Lockfile:
    name: str
    pid: int
    port: int
    password: str = field(repr=False)

    @classmethod
    def parse(cls, text: str):
        try:
            name, pid, port, password, protocol = text.strip().split(":")
            if not name or int(pid) <= 0 or not 1 <= int(port) <= 65535 or not password or protocol != "https":
                raise ValueError
            return cls(name, int(pid), int(port), password)
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid Riot Client lockfile") from error


@dataclass(frozen=True)
class Session:
    puuid: str
    access_token: str = field(repr=False)
    entitlement_token: str = field(repr=False)
    shard: str
    region: str
    version: str
    running: bool = False

    def __post_init__(self):
        if self.shard not in SHARDS or not re.fullmatch(r"[a-z]{2,8}", self.region):
            raise ValueError("Unknown region/shard")
        UUID(self.puuid)

    @property
    def cache_key(self) -> str:
        return f"{self.puuid}:{self.shard}"

    def context(self) -> dict:
        return {key: getattr(self, key) for key in ("puuid", "shard", "region", "version")}


class RiotError(Exception):
    def __init__(self, status: int, code: str = "", retry_after: float | None = None):
        self.status, self.code, self.retry_after = status, code, retry_after
        super().__init__(f"Riot API: HTTP {status}")

    @property
    def authentication_failure(self) -> bool:
        return self.status == 401 or self.status == 400 and self.code == "BAD_CLAIMS" or self.status == 403 and self.code == "MISSING_ENTITLEMENT"


def check_response(response: httpx.Response):
    if response.is_success:
        return
    retry = None
    value = response.headers.get("Retry-After")
    if value is not None:
        try:
            retry = max(0, float(value))
        except ValueError:
            try:
                retry = max(0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    try:
        payload = response.json()
        code = payload.get("errorCode", "") if isinstance(payload, dict) else ""
    except ValueError:
        code = ""
    # Do not copy request headers or arbitrary response text into errors/logs.
    raise RiotError(response.status_code, str(code), retry)


class LocalRiotClient:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

    async def authenticate(self, lock: Lockfile, version: str) -> Session:
        # Only this fixed loopback client accepts Riot's local self-signed certificate.
        async with httpx.AsyncClient(base_url=f"https://127.0.0.1:{lock.port}", verify=False,
                                     auth=("riot", lock.password), transport=self.transport,
                                     follow_redirects=False, trust_env=False, timeout=5) as client:
            response = await client.get("/entitlements/v1/token")
            check_response(response)
            tokens = response.json()
            response = await client.get("/product-session/v1/external-sessions")
            check_response(response)
            region = shard = None
            running = False
            for session in response.json().values():
                if session.get("productId") != "valorant":
                    continue
                running |= str(session.get("phase", "")).lower() == "running"
                for arg in session.get("launchConfiguration", {}).get("arguments", []):
                    if arg.startswith("-ares-shard="):
                        shard = arg.split("=", 1)[1].lower()
                    elif arg.startswith("-ares-deployment="):
                        region = arg.split("=", 1)[1].lower()
            if not region or not shard:
                raise ValueError("Launch VALORANT to determine the region/shard")
            if not version or not tokens.get("accessToken") or not tokens.get("token"):
                raise ValueError("Could not obtain a local Riot session")
            return Session(tokens["subject"], tokens["accessToken"], tokens["token"], shard, region, version, running)


class SessionProvider(Protocol):
    async def discover(self) -> Session | None: ...
    def invalidate(self) -> None: ...


class WaitingProvider:
    """Replace with Windows discovery; safe on every development OS."""
    async def discover(self):
        return None

    def invalidate(self):
        pass


class FileSessionProvider:
    """Explicit --lockfile for integration/testing, not automatic OS discovery."""
    def __init__(self, path: Path, catalog: "Catalog", local: LocalRiotClient | None = None):
        self.path, self.catalog = path, catalog
        self.local = local or LocalRiotClient()
        self._fingerprint = None
        self._cached: Session | None = None
        self._expires = 0.0

    def invalidate(self):
        self._expires = 0

    async def discover(self):
        try:
            text = await asyncio.to_thread(self.path.read_text)
        except FileNotFoundError:
            self._cached, self._fingerprint = None, None
            return None
        lock = Lockfile.parse(text)
        fingerprint = hashlib.sha256(text.encode()).digest()
        if self._cached and self._fingerprint == fingerprint and time.monotonic() < self._expires:
            return self._cached
        await self.catalog.load()
        if not self.catalog.version:
            raise ValueError("Could not determine the Riot client version")
        self._cached = await self.local.authenticate(lock, self.catalog.version)
        self._fingerprint, self._expires = fingerprint, time.monotonic() + 45
        return self._cached


class RiotClient:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.http = client or httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False)
        self._limit = asyncio.Semaphore(2)
        self._limited_until = 0.0

    async def close(self):
        await self.http.aclose()

    async def get(self, session: Session, path: str, *, glz: bool = False) -> dict:
        if "://" in path or ".." in path or path.startswith("//"):
            raise ValueError("Only Riot endpoint paths are accepted")
        host = f"glz-{session.region}-1.{session.shard}.a.pvp.net" if glz else f"pd.{session.shard}.a.pvp.net"
        async with self._limit:
            if delay := max(0, self._limited_until - time.monotonic()):
                await asyncio.sleep(delay)
            response = await self.http.get(f"https://{host}/{path.lstrip('/')}", headers={
                "Authorization": f"Bearer {session.access_token}",
                "X-Riot-Entitlements-JWT": session.entitlement_token,
                "X-Riot-ClientPlatform": PLATFORM, "X-Riot-ClientVersion": session.version,
            })
            try:
                check_response(response)
            except RiotError as error:
                if error.status == 429:
                    self._limited_until = time.monotonic() + (error.retry_after if error.retry_after is not None else 30)
                raise
            return response.json()

    async def mmr(self, session: Session):
        return await self.get(session, f"mmr/v1/players/{session.puuid}")

    async def history(self, session: Session, cursor: int):
        return await self.get(session, f"match-history/v1/history/{session.puuid}?startIndex={cursor}&endIndex={cursor + 20}&queue=competitive")

    async def updates(self, session: Session, cursor: int):
        return await self.get(session, f"mmr/v1/players/{session.puuid}/competitiveupdates?startIndex={cursor}&endIndex={cursor + 20}&queue=competitive")

    async def details(self, session: Session, match_id: str):
        return await self.get(session, f"match-details/v1/matches/{quote(str(UUID(match_id)), safe='')}")


def rank_name(tier: int) -> str:
    names = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "DIAMOND", "ASCENDANT", "IMMORTAL"]
    if 3 <= tier <= 26:
        return f"{names[(tier - 3) // 3]} {(tier - 3) % 3 + 1}"
    return "RADIANT" if tier == 27 else "UNRANKED" if 0 <= tier < 3 else "UNKNOWN RANK"


def parse_match(payload: dict, puuid: str, delta: int | None, catalog: "Catalog | None" = None) -> Match | None:
    info = payload.get("matchInfo", {})
    if not info.get("isCompleted") or payload.get("hasTempValues"):
        return None
    player = next((p for p in payload.get("players", []) if p.get("subject") == puuid), None)
    if not player or not isinstance(stats := player.get("stats"), dict):
        return None
    fields = ("kills", "deaths", "assists", "score", "roundsPlayed")
    if any(type(stats.get(key)) is not int or stats[key] < 0 for key in fields):
        return None
    completion = str(info.get("completionState", "")).lower()
    outcome = "unknown"
    if completion == "votedraw":
        outcome = "draw"
    elif any(t.get("teamId") == player.get("teamId") and t.get("won") for t in payload.get("teams", [])):
        outcome = "win"
    elif any(t.get("teamId") != player.get("teamId") and t.get("won") for t in payload.get("teams", [])):
        outcome = "loss"
    agent, map_id = player.get("characterId", ""), info.get("mapId", "")
    return Match(id=info["matchId"], started_at=info["gameStartMillis"], season_id=info["seasonId"],
                 queue=info["queueID"], map=catalog.maps.get(map_id, map_id.rsplit("/", 1)[-1]) if catalog else map_id.rsplit("/", 1)[-1],
                 agent=catalog.agents.get(agent, "Agent") if catalog else "Agent", agent_id=agent or None,
                 outcome=outcome, kills=stats["kills"], deaths=stats["deaths"], assists=stats["assists"],
                 score=stats["score"], rounds=stats["roundsPlayed"], rating_delta=delta,
                 is_remake=completion == "remake")


class Catalog:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.http = client
        self.agents: dict[str, str] = {}
        self.maps: dict[str, str] = {}
        self.seasons: list[dict] = []
        self.version: str | None = None
        self._loaded_until = 0.0

    @property
    def active_season(self) -> str | None:
        now = datetime.now(UTC)
        for season in self.seasons:
            if season.get("parentUuid") and datetime.fromisoformat(season["startTime"]) <= now < datetime.fromisoformat(season["endTime"]):
                return season["uuid"]
        return None

    def rank(self, mmr: dict) -> Rank:
        season = self.active_season
        info = mmr.get("QueueSkills", {}).get("competitive", {}).get("SeasonalInfoBySeasonID", {}).get(season, {})
        tier = info.get("CompetitiveTier", 0)
        return Rank(name=rank_name(tier) if season else "UNKNOWN RANK", tier=tier,
                    rr=info.get("RankedRating") if tier >= 3 else None,
                    leaderboard=info.get("LeaderboardRank") if info.get("LeaderboardRank", 0) > 0 else None,
                    season_id=season, season_name=next((s.get("displayName") for s in self.seasons if s["uuid"] == season), None))

    async def load(self):
        if self._loaded_until > time.monotonic():
            return
        own_client = self.http is None
        client = self.http or httpx.AsyncClient(timeout=10, trust_env=False)
        try:
            for kind in ("version", "agents", "maps", "seasons"):
                response = await client.get(f"https://valorant-api.com/v1/{kind}")
                response.raise_for_status()
                data = response.json()["data"]
                if kind == "version": self.version = data["riotClientVersion"]
                elif kind == "agents": self.agents = {a["uuid"]: a["displayName"] for a in data}
                elif kind == "maps": self.maps = {m["mapUrl"]: m["displayName"] for m in data}
                else: self.seasons = data
            self._loaded_until = time.monotonic() + 3600
        finally:
            if own_client:
                await client.aclose()
