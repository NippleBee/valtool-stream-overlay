import asyncio

import httpx
import pytest

from valtool_overlay.models import Settings
from valtool_overlay.riot import RiotClient, Session
from valtool_overlay.service import OverlayService, RiotWorker
from valtool_overlay.storage import Storage
from conftest import PUUID, detail, mid


@pytest.mark.asyncio
async def test_independent_pagination_cached_details_and_delayed_rr(tmp_path, session, catalog):
    store=Storage(tmp_path)
    store.save_settings(Settings(matchCount=None))
    service=OverlayService(store)
    history_cursors=[]
    rating_cursors=[]
    detail_calls=[]
    ready=False
    def handle(request):
        path=request.url.path
        if path.endswith('/competitiveupdates'):
            cursor=int(request.url.params['startIndex']); rating_cursors.append(cursor)
            # RR history contains fewer entries than match history. Never share its cursor.
            return httpx.Response(200,json={'Matches':[{'MatchID':mid(i),'RankedRatingEarned':23 if i%2==0 else -12,'PerformanceBonus':7} for i in range(25) if ready or i!=0][cursor:cursor+20]})
        if '/match-history/' in path:
            cursor=int(request.url.params['startIndex']); history_cursors.append(cursor)
            return httpx.Response(200,json={'History':[{'MatchID':mid(i)} for i in range(25)][cursor:cursor+10], 'EndIndex':min(cursor+10,25),'Total':25})
        if '/match-details/' in path:
            index=int(path.rsplit('/',1)[1].replace('-',''),16)-1; detail_calls.append(index)
            payload=detail(index)
            payload['hasTempValues'] = True  # Current Riot metadata must not block valid completed stats or caching.
            if index==1 and not ready:
                payload['players'][0]['stats']=None
            return httpx.Response(200,json=payload)
        return httpx.Response(200,json={'QueueSkills':{'competitive':{'SeasonalInfoBySeasonID':{'current':{'CompetitiveTier':19,'RankedRating':64}}}}})
    client=RiotClient(httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    worker=RiotWorker(service,client,catalog=catalog)
    try:
        await worker.sync(session)
        assert history_cursors==[0,10,20]
        assert rating_cursors==[0,20]
        assert service.snapshot().stats.games==24 and not service.snapshot().stats.is_complete
        assert service.snapshot().stats.last_delta is None
        assert service.pending_details
        assert len(store.read_matches(session.cache_key)) == 24
        ready=True
        history_cursors.clear(); rating_cursors.clear(); detail_calls.clear()
        await worker.sync(session)
        snapshot=service.snapshot()
        assert detail_calls==[1]  # Only the detail previously missing player stats is fetched again.
        assert snapshot.stats.games==25 and snapshot.stats.is_complete
        assert snapshot.stats.last_delta==23  # Performance bonus is already in Earned.
        assert not service.pending_details
        assert len(Storage(tmp_path).read_matches(session.cache_key))==25
        assert 'private' not in str(store.read_context(session.puuid))
        other=Session('22222222-2222-4222-8222-222222222222','a','e','eu','eu','v')
        assert store.read_matches(other.cache_key)==[]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_monitor_cancels_sync_when_credentials_rotate(tmp_path, session, catalog):
    from dataclasses import replace
    changed = asyncio.Event()
    class Provider:
        calls = 0
        async def discover(self):
            self.calls += 1
            if self.calls == 1:
                return session
            changed.set()
            return replace(session, access_token='rotated-access')
    client = RiotClient()
    worker = RiotWorker(OverlayService(Storage(tmp_path)), client, Provider(), catalog)
    task = asyncio.create_task(worker._monitor())
    try:
        await asyncio.sleep(.01)
        worker._wakeup.clear()
        worker._sync_task = asyncio.create_task(asyncio.sleep(100))
        await asyncio.wait_for(changed.wait(), 3)
        await asyncio.sleep(0)
        assert worker._sync_task.cancelled()
        assert worker.session.access_token == 'rotated-access'
        assert worker._wakeup.is_set()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await client.close()


@pytest.mark.asyncio
async def test_unroutable_new_account_clears_old_snapshot(tmp_path, session, catalog):
    from valtool_overlay.riot import SessionNotReady
    changed = asyncio.Event()
    class Provider:
        calls = 0
        async def discover(self):
            self.calls += 1
            if self.calls == 1:
                return session
            changed.set()
            raise SessionNotReady('22222222-2222-4222-8222-222222222222')
    client = RiotClient()
    service = OverlayService(Storage(tmp_path))
    worker = RiotWorker(service, client, Provider(), catalog)
    task = asyncio.create_task(worker._monitor())
    try:
        await asyncio.sleep(.01)
        service.records = {'old': __import__('conftest').record()}
        service.rank = catalog.rank({})
        await asyncio.wait_for(changed.wait(), 3)
        assert worker.session is None
        assert not service.records and service.rank is None
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await client.close()


@pytest.mark.asyncio
async def test_preview_does_not_change_live_data_or_publish_secrets(tmp_path):
    service=OverlayService(Storage(tmp_path))
    live=service.snapshot()
    assert live.mode=='live' and live.rank is None and live.stats.games==0
    preview=service.snapshot(True)
    assert preview.mode=='demo' and preview.stats.games==20
    assert service.snapshot()==live
    queue=service.subscribe()
    first=await queue.get()
    await service.update_settings(Settings(matchCount=1))
    assert await queue.get()>first
    assert service.snapshot(True).stats.games==1 and service.snapshot().stats.games==0
    service.unsubscribe(queue)
    assert not service._subscribers


@pytest.mark.asyncio
async def test_incomplete_recent_window_does_not_scan_entire_archive(tmp_path, session, catalog):
    calls = []
    def handle(request):
        path = request.url.path
        calls.append(path)
        if path.endswith('/competitiveupdates'):
            return httpx.Response(200, json={'Matches': []})
        if '/match-history/' in path:
            return httpx.Response(200, json={'History': [{'MatchID': mid(i)} for i in range(20)], 'EndIndex': 20, 'Total': 66})
        if '/match-details/' in path:
            index = int(path.rsplit('/', 1)[1].replace('-', ''), 16) - 1
            payload = detail(index)
            payload['players'][0]['stats'] = None
            return httpx.Response(200, json=payload)
        return httpx.Response(200, json={})
    client = RiotClient(httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    service = OverlayService(Storage(tmp_path))
    try:
        await RiotWorker(service, client, catalog=catalog).sync(session)
        assert sum('/match-history/' in path for path in calls) == 1
        assert sum('/match-details/' in path for path in calls) == 20
        assert not service.records and service.pending_details
        assert service.snapshot().stats.games == 0
        assert not service.snapshot().stats.is_complete
        assert not service.storage.read_matches(session.cache_key)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_rate_limit_retries_same_request_without_restarting_sync(tmp_path, session, catalog):
    from valtool_overlay.riot import RiotError
    service = OverlayService(Storage(tmp_path))
    client = RiotClient()
    worker = RiotWorker(service, client, catalog=catalog)
    entered = asyncio.Event()
    calls = []
    async def request(value):
        calls.append(value)
        if len(calls) == 1:
            entered.set()
            raise RiotError(429, retry_after=.01)
        return {'result': value}
    try:
        assert await worker._request(request, 20) == {'result': 20}
        assert calls == [20, 20]
        async def limited():
            entered.set()
            raise RiotError(429, retry_after=60)
        entered.clear()
        task = asyncio.create_task(worker._request(limited))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_monitor_clears_previous_account_and_cancels_inflight_sync(tmp_path, session, catalog):
    service=OverlayService(Storage(tmp_path))
    switched=asyncio.Event()
    class Provider:
        calls=0
        async def discover(self):
            self.calls+=1
            if self.calls==1: return session
            switched.set()
            return Session('22222222-2222-4222-8222-222222222222','a','e','eu','eu','v')
        def invalidate(self): pass
    client=RiotClient(httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={}))))
    worker=RiotWorker(service,client,Provider(),catalog)
    task=asyncio.create_task(worker._monitor())
    try:
        await asyncio.sleep(.01)
        service.rank=catalog.rank({})
        service.records={'old': __import__('conftest').record()}
        worker._sync_task=asyncio.create_task(asyncio.sleep(100))
        await asyncio.wait_for(switched.wait(),3)
        assert worker.session.puuid!=PUUID
        assert service.records=={} and service.rank is None
        await asyncio.sleep(0)
        assert worker._sync_task.cancelled()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        await client.close()
