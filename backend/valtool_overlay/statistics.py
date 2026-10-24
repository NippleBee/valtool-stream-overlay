from collections.abc import Iterable

from .models import Match, Settings, Stats


def calculate(source: Iterable[Match], settings: Settings, season: str | None, history_complete: bool = True) -> tuple[Stats, list[Match]]:
    unique = {m.id: m for m in source if m.is_final and not m.is_remake
              and m.queue == "competitive" and m.outcome in {"win", "loss", "draw"}
              and (settings.scope != "act" or season is not None and m.season_id == season)}
    available = sorted(unique.values(), key=lambda m: (-m.started_at, m.id))
    selected = available[:settings.match_count] if settings.match_count is not None else available
    games = len(selected)
    kills = sum(m.kills for m in selected)
    deaths = sum(m.deaths for m in selected)
    assists = sum(m.assists for m in selected)
    score = sum(m.score for m in selected)
    rounds = sum(m.rounds for m in selected)
    wins = sum(m.outcome == "win" for m in selected)
    ratings = [m.rating_delta for m in selected if m.rating_delta is not None]
    return Stats(
        games=games, wins=wins, losses=sum(m.outcome == "loss" for m in selected),
        draws=sum(m.outcome == "draw" for m in selected), kills=kills, deaths=deaths, assists=assists,
        kd=kills / max(1, deaths) if games else None,
        kda_ratio=(kills + assists) / max(1, deaths) if games else None,
        acs=score / rounds if rounds else None, winrate=wins / games * 100 if games else None,
        rr_gain=sum(r for r in ratings if r > 0) if ratings else None,
        rr_loss=sum(r for r in ratings if r < 0) if ratings else None,
        rr_net=sum(ratings) if ratings else None,
        last_delta=selected[0].rating_delta if games else None,
        rr_covered=len(ratings), requested=settings.match_count, available=len(available),
        is_complete=history_complete or settings.match_count is not None and games >= settings.match_count,
    ), available[:settings.recent_count]
