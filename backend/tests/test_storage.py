import json
import sqlite3

import pytest

from valtool_overlay.models import Settings
from valtool_overlay.storage import Storage
from conftest import record


def test_legacy_database_and_settings_survive_restart(tmp_path):
    key = 'a'*48
    legacy = Settings(title='Saved', matchCount=7).json_data() | {'autoStart': True}
    legacy.pop('showWatermark')
    legacy.pop('renderScale')
    tmp_path.joinpath('settings.json').write_text(json.dumps(dict(schemaVersion=1, port=32145, overlayKey=key,
                                                                 overlay=legacy)))
    with sqlite3.connect(tmp_path/'matches.db') as db:
        db.execute('CREATE TABLE matches (account TEXT NOT NULL,id TEXT NOT NULL,started INTEGER NOT NULL,data TEXT NOT NULL,PRIMARY KEY(account,id))')
        db.execute('INSERT INTO matches VALUES(?,?,?,?)', ('one:eu','a',1,json.dumps(record().json_data())))
    store = Storage(tmp_path)
    assert store.configuration.overlay_key == key
    assert store.configuration.overlay.match_count == 7
    assert store.configuration.overlay.show_watermark is True
    assert store.configuration.overlay.render_scale == 2
    assert store.read_matches('one:eu')[0].id == 'a'
    store.save_match('two:eu', record(kills=99))
    store.save_match('one:eu', record(ratingDelta=-12))
    store.save_settings(Settings(title='Restart', matchCount=None, showWatermark=False, renderScale=3))
    restarted = Storage(tmp_path)
    assert restarted.configuration.overlay_key == key
    assert restarted.configuration.overlay.title == 'Restart'
    assert restarted.configuration.overlay.match_count is None
    assert restarted.configuration.overlay.show_watermark is False
    assert restarted.configuration.overlay.render_scale == 3
    assert restarted.read_matches('one:eu')[0].rating_delta == -12
    assert restarted.read_matches('two:eu')[0].kills == 99
    assert restarted.read_matches('one:na') == []
    assert 'autoStart' not in json.loads(tmp_path.joinpath('settings.json').read_text())['overlay']


def test_credentials_not_persisted_and_corrupt_settings_preserved(tmp_path):
    store = Storage(tmp_path)
    store.save_context('a', dict(puuid='a',shard='eu',version='release',accessToken='secret',password='secret'))
    assert store.read_context('a') == dict(puuid='a',shard='eu',version='release')
    with pytest.raises(ValueError):
        store.save_match('a', record(isFinal=False))
    store.path.write_text('{broken')
    with pytest.raises(ValueError):
        Storage(tmp_path)
    assert store.path.read_text() == '{broken'
