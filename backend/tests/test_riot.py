import asyncio
import base64
import json
import time

import httpx
import pytest

from valtool_overlay.riot import Lockfile, LocalRiotClient, FileSessionProvider, RiotClient, RiotError, parse_match, rank_name
from conftest import PUUID, detail


@pytest.mark.parametrize('text', ['Riot:0:50000:secret:https', 'Riot:1:70000:secret:https', 'Riot:1:50000:secret:http', 'Riot:1:50000:secret'])
def test_invalid_lockfile(text):
    with pytest.raises(ValueError, match='lockfile'):
        Lockfile.parse(text)


@pytest.mark.asyncio
async def test_local_tokens_and_explicit_provider_rotation(tmp_path, catalog):
    requests = []
    def handle(request):
        requests.append(request)
        assert request.url.host == '127.0.0.1' and request.url.scheme == 'https'
        assert request.headers['authorization'] == 'Basic '+base64.b64encode(b'riot:secret').decode()
        if request.url.path == '/entitlements/v1/token':
            return httpx.Response(200, json=dict(subject=PUUID,accessToken='private-access',token='private-entitlement'))
        return httpx.Response(200, json={'session':dict(productId='valorant', phase='Running', launchConfiguration={'arguments':['-ares-shard=eu','-ares-deployment=eu']})})
    path = tmp_path/'lockfile'
    path.write_text('Riot:123:50000:secret:https')
    local = LocalRiotClient(transport=httpx.MockTransport(handle))
    provider = FileSessionProvider(path, catalog, local)
    session = await provider.discover()
    assert session.running and session.region == session.shard == 'eu'
    assert 'secret' not in repr(Lockfile.parse(path.read_text()))
    assert 'private' not in repr(session)
    assert await provider.discover() is session
    assert len(requests) == 2
    provider.invalidate()
    await provider.discover()
    assert len(requests) == 4
    path.write_text('Riot:124:50001:secret:https')
    await provider.discover()
    assert requests[-1].url.port == 50001
    path.unlink()
    assert await provider.discover() is None


@pytest.mark.asyncio
async def test_remote_headers_hosts_and_429_backoff(session):
    calls=[]
    def handle(request):
        calls.append(time.monotonic())
        assert request.url.host == 'pd.eu.a.pvp.net'
        assert request.headers['authorization'] == 'Bearer private-access'
        assert request.headers['x-riot-entitlements-jwt'] == 'private-entitlement'
        assert request.headers['x-riot-clientversion'] == 'release-fixture'
        assert json.loads(base64.b64decode(request.headers['x-riot-clientplatform']))['platformType'] == 'PC'
        return httpx.Response(429, headers={'Retry-After':'.02'}) if len(calls)==1 else httpx.Response(200,json={})
    client=RiotClient(httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    try:
        with pytest.raises(RiotError) as error:
            await client.mmr(session)
        assert error.value.retry_after == .02
        await client.mmr(session)
        assert calls[1]-calls[0] >= .018
        with pytest.raises(ValueError):
            await client.get(session,'https://evil.example')
    finally:
        await client.close()


@pytest.mark.parametrize('status,code,auth', [(401,'',True),(403,'FORBIDDEN',False),(403,'MISSING_ENTITLEMENT',True),(400,'BAD_CLAIMS',True),(429,'',False)])
@pytest.mark.asyncio
async def test_http_failures_are_typed_and_sanitized(session,status,code,auth):
    client=RiotClient(httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status,json={'errorCode':code,'message':'private-access'}))))
    try:
        with pytest.raises(RiotError) as error:
            await client.mmr(session)
        assert error.value.authentication_failure is auth
        assert 'private-access' not in str(error.value)
    finally:
        await client.close()


def test_final_detail_surrender_draw_remake_and_rank(catalog):
    payload=detail()
    match=parse_match(payload,PUUID,23,catalog)
    assert match.rating_delta==23 and match.outcome=='win' and not match.is_remake
    assert parse_match(payload,'someone-else',None,catalog) is None
    payload['hasTempValues']=True
    assert parse_match(payload,PUUID,23,catalog) is None
    payload['hasTempValues']=False
    payload['matchInfo']['completionState']='VoteDraw'
    assert parse_match(payload,PUUID,None,catalog).outcome=='draw'
    payload['matchInfo']['completionState']='Remake'
    assert parse_match(payload,PUUID,None,catalog).is_remake
    assert rank_name(19)=='DIAMOND 2' and rank_name(27)=='RADIANT'
    mmr={'QueueSkills':{'competitive':{'SeasonalInfoBySeasonID':{'old':{'CompetitiveTier':27},'current':{'CompetitiveTier':19,'RankedRating':64,'LeaderboardRank':12}}}}}
    assert catalog.rank(mmr).rr==64 and catalog.rank(mmr).leaderboard==12
