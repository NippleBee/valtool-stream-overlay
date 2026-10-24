import pytest
from pydantic import ValidationError

from valtool_overlay.models import Settings
from valtool_overlay.statistics import calculate
from conftest import record


def test_weighted_ratios():
    stats, _ = calculate([record('a', 2, kills=20, deaths=2, score=3000),
                          record('b', 1, kills=10, deaths=10, score=2000, rounds=20)], Settings(), 'current')
    assert stats.kd == 2.5
    assert stats.kda_ratio == pytest.approx(38/12)
    assert stats.acs == pytest.approx(5000/30)


def test_filter_before_take_and_independent_strip():
    matches = [record('a', 100, seasonId='old'), record('b', 90, isFinal=False), record('c', 80, isRemake=True),
               record('d', 70, queue='unrated'), record('e', 60), record('f', 50)]
    stats, recent = calculate(matches, Settings(scope='act', matchCount=1), 'current')
    assert (stats.games, stats.available) == (1, 2)
    assert [m.id for m in recent] == ['e', 'f']
    assert calculate(matches, Settings(scope='act'), None)[0].games == 0


def test_draws_dedup_and_missing_latest_rr():
    a = record('a', 3, ratingDelta=None)
    stats, _ = calculate([a, a, record('b', 2, outcome='loss', ratingDelta=-19),
                          record('c', 1, outcome='draw', ratingDelta=24), record('d', 0, outcome='unknown')],
                         Settings(matchCount=None), 'current')
    assert (stats.games, stats.wins, stats.losses, stats.draws) == (3, 1, 1, 1)
    assert stats.winrate == pytest.approx(100/3)
    assert (stats.rr_gain, stats.rr_loss, stats.rr_net, stats.rr_covered, stats.last_delta) == (24, -19, 5, 2, None)


def test_missing_and_zero_deaths():
    empty, _ = calculate([], Settings(), None, False)
    assert empty.kd is empty.acs is empty.rr_gain is None
    assert not empty.is_complete
    zero, _ = calculate([record(deaths=0, rounds=0)], Settings(), 'current')
    assert zero.kd == 10 and zero.acs is None
    assert calculate([record()], Settings(matchCount=1), 'current', False)[0].is_complete


@pytest.mark.parametrize('patch', [{'accent':'url(https://example.com)'}, {'layout':'mini'}, {'matchCount':0},
                                  {'matchCount':True}, {'opacity':float('nan')}, {'metrics':['kd','kd']},
                                  {'showMatches':'false'}, {'title':'bad\ntext'}])
def test_invalid_settings(patch):
    with pytest.raises(ValidationError):
        Settings.model_validate(Settings().json_data() | patch)
