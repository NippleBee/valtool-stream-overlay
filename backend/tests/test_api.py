import json
from urllib.parse import urlsplit

import httpx
import pytest

from valtool_overlay.app import create_app
from valtool_overlay.models import Settings
from valtool_overlay.riot import WaitingProvider


@pytest.fixture(autouse=True)
def offline_discovery(monkeypatch):
    monkeypatch.setattr('valtool_overlay.windows.WindowsSessionProvider', lambda catalog: WaitingProvider())


@pytest.mark.asyncio
async def test_editor_auth_validation_demo_isolation_and_restart(tmp_path):
    app=create_app(tmp_path)
    origin='http://127.0.0.1:32145'
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=origin) as client:
        assert (await client.get('/api/editor')).status_code==401
        token=urlsplit(app.state.security.new_editor_url()).fragment.split('=')[1]
        headers={'Origin':origin,'Authorization':'Bearer '+token}
        assert (await client.post('/api/session',headers=headers)).status_code==204
        assert (await client.post('/api/session',headers=headers)).status_code==401
        editor=(await client.get('/api/editor')).json()
        output=editor['overlayUrl'].replace('/overlay/','/api/overlay/')
        live=(await client.get(output)).json()
        assert live['mode']=='live' and live['stats']['games']==0
        preview=(await client.get(output+'?preview=demo')).json()
        assert preview['mode']=='demo' and preview['stats']['games']==20
        assert (await client.get(output)).json()==live
        assert (await client.get('/api/overlay/bad')).status_code==404
        assert (await client.get('/api/overlay/é')).status_code==404
        assert (await client.get('/api/health',headers={'Host':'evil.example'})).status_code==403
        assert (await client.put('/api/settings',json=Settings().json_data(),headers={'Origin':'https://evil.example'})).status_code==403
        for patch in ({'metrics':None},{'layout':'mini'},{'accent':'url(x)'},{'matchCount':0}):
            assert (await client.put('/api/settings',json=Settings().json_data()|patch,headers={'Origin':origin})).status_code==400
        saved=Settings(title='Persistent',matchCount=1).json_data()
        assert (await client.put('/api/settings',json=saved,headers={'Origin':origin})).status_code==200
        assert (await client.get(output+'?preview=demo')).json()['stats']['games']==1
        assert 'accessToken' not in (await client.get(output)).text
    restarted=create_app(tmp_path)
    assert restarted.state.storage.configuration.overlay_key==app.state.storage.configuration.overlay_key
    assert restarted.state.service.settings.title=='Persistent'
    await restarted.state.worker.client.close()
