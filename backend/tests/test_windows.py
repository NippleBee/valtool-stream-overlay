import base64
import json
import sys

import httpx
import pytest

from conftest import PUUID
from valtool_overlay.riot import LocalRiotClient
from valtool_overlay.runtime import InstanceLock, default_frontend_dir
from valtool_overlay.windows import WindowsSessionProvider, installed_version


def token(subject=PUUID, shard="eu"):
    claims = base64.urlsafe_b64encode(json.dumps({"sub": subject, "pp": {"c": shard}}).encode()).decode().rstrip("=")
    return f"header.{claims}.signature"


@pytest.mark.asyncio
async def test_discovery_lifecycle_token_rotation_and_independent_routing(tmp_path, catalog):
    path = tmp_path / "Riot Games/Riot Client/Config/lockfile"
    path.parent.mkdir(parents=True)
    path.write_text("Riot:123:50000:secret:https")
    current = {}
    calls = []
    subject = PUUID
    arguments = ["-ares-deployment=latam"]
    def handle(request):
        calls.append(request)
        if request.url.path == "/entitlements/v1/token":
            return httpx.Response(200, json={"subject": subject, "accessToken": token(subject, "na"), "token": "entitlement"})
        # Real Windows session: phase Idle despite the live game process.
        return httpx.Response(200, json={"game": {"productId": "valorant", "phase": "Idle",
                                                  "launchConfiguration": {"arguments": arguments}}})
    provider = WindowsSessionProvider(catalog, LocalRiotClient(transport=httpx.MockTransport(handle)),
                                      directory=tmp_path, process_reader=lambda: current)
    assert await provider.discover() is None
    assert not calls  # A stale lockfile must not cause network traffic.
    current[123] = "riotclientservices.exe"
    current[456] = "valorant-win64-shipping.exe"
    session = await provider.discover()
    assert session.running and session.shard == "na" and session.region == "latam"
    current.pop(456)
    arguments.clear()
    session = await provider.discover()
    assert not session.running and session.region == "latam"
    subject = "22222222-2222-4222-8222-222222222222"
    with pytest.raises(ValueError, match="region/shard"):
        await provider.discover()  # No region borrowed from the previous account.
    arguments.append("-ares-deployment=br")
    assert (await provider.discover()).puuid == subject
    path.write_text("Riot:789:50001:secret:https")
    assert await provider.discover() is None
    current[789] = current.pop(123)
    await provider.discover()
    assert calls[-1].url.port == 50001
    current.clear()
    before = len(calls)
    assert await provider.discover() is None
    assert len(calls) == before


@pytest.mark.asyncio
async def test_lockfile_replacement_during_authentication(tmp_path, catalog):
    path = tmp_path / "Riot Games/Riot Client/Config/lockfile"
    path.parent.mkdir(parents=True)
    path.write_text("Riot:123:50000:secret:https")
    def handle(request):
        if request.url.path == "/entitlements/v1/token":
            return httpx.Response(200, json={"subject": PUUID, "accessToken": token(), "token": "entitlement"})
        path.write_text("Riot:456:50001:new-secret:https")
        return httpx.Response(200, json={"game": {"productId": "valorant",
                                                  "launchConfiguration": {"arguments": ["-ares-deployment=eu"]}}})
    provider = WindowsSessionProvider(catalog, LocalRiotClient(transport=httpx.MockTransport(handle)),
                                      directory=tmp_path, process_reader=lambda: {123: "riotclientservices.exe"})
    assert await provider.discover() is None


def test_installed_version_and_frozen_paths(tmp_path, monkeypatch):
    log = tmp_path / "VALORANT/Saved/Logs/ShooterGame.log"
    log.parent.mkdir(parents=True)
    assert installed_version(tmp_path) is None
    log.write_text("LogShooter: Display: Branch: release-13.08\n"
                   "LogShooter: Display: Changelist: 5760300\n"
                   "LogShooter: Display: Build version: 22\n")
    assert installed_version(tmp_path) == "release-13.08-shipping-22-5760300"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert default_frontend_dir() == tmp_path / "frontend/dist"


def test_single_instance_does_not_touch_existing_settings(tmp_path):
    path = tmp_path / "Ścieżka with spaces"
    path.mkdir()
    settings = path / "settings.json"
    settings.write_text("unchanged")
    with InstanceLock(path):
        with pytest.raises(OSError, match="already running"):
            with InstanceLock(path):
                pytest.fail("Acquired a lock already held by another instance")
        assert settings.read_text() == "unchanged"
    with InstanceLock(path):
        pass
