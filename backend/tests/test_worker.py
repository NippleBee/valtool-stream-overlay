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
            if index==1 and not ready:
                payload['hasTempValues']=True
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
        ready=True
        history_cursors.clear(); rating_cursors.clear(); detail_calls.clear()
        await worker.sync(session)
        snapshot=service.snapshot()
        assert detail_calls==[1]  # Only the previously temporary detail is fetched again.
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
