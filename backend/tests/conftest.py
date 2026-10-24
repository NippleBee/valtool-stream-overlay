from uuid import UUID

import pytest

from valtool_overlay.models import Match
from valtool_overlay.riot import Catalog, Session

PUUID = '11111111-1111-4111-8111-111111111111'


def mid(index):
    return str(UUID(int=index + 1))


def record(id='a', time=1, **changes):
    return Match.model_validate(dict(id=id, startedAt=time, seasonId='current', map='Ascent', agent='Jett',
                                    outcome='win', kills=10, deaths=5, assists=4, score=2000,
                                    rounds=10, ratingDelta=20) | changes)


def detail(index=0, **info):
    return {'matchInfo': dict(matchId=mid(index), isCompleted=True, gameStartMillis=100000-index,
                             seasonId='current', queueID='competitive', mapId='/Game/Maps/Ascent/Ascent',
                             completionState='Surrendered', isEarlyCompletion=True) | info,
            'players': [{'subject': PUUID, 'teamId': 'Blue', 'characterId': 'agent',
                         'stats': dict(kills=20, deaths=10, assists=5, score=4000, roundsPlayed=20)}],
            'teams': [{'teamId': 'Blue', 'won': True}, {'teamId': 'Red', 'won': False}],
            'hasTempValues': False}


@pytest.fixture
def session():
    return Session(PUUID, 'private-access', 'private-entitlement', 'eu', 'eu', 'release-fixture', True)


@pytest.fixture
def catalog():
    catalog = Catalog()
    catalog._loaded_until = float('inf')
    catalog.version = 'release-fixture'
    catalog.seasons = [{'uuid': 'current', 'parentUuid': 'episode', 'startTime': '2020-01-01T00:00:00Z',
                        'endTime': '2100-01-01T00:00:00Z', 'displayName': 'Fixture Act'}]
    catalog.agents = {'agent': 'Jett'}
    catalog.maps = {'/Game/Maps/Ascent/Ascent': 'Ascent'}
    return catalog
