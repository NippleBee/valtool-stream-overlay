"""Deterministic sample data, shared by demo mode and preview. Never replaces live data."""

from datetime import UTC, datetime

from .models import Match, Rank

RANK = Rank(name="DIAMOND 2", tier=19, rr=64, season_id="demo-act", season_name="ACT V")
AGENTS = [
    ("Jett", "add6443a-41bd-e414-f6ad-e58d267f4e95"),
    ("Clove", "1dbf2edd-4729-0984-3115-daa5eed44993"),
    ("Sova", "320b2a48-4d9b-a075-30f1-1f93a9b638fa"),
    ("Reyna", "a3bfb853-43b2-7238-a4f1-ad90e9e46bcc"),
    ("Omen", "8e253930-4c05-31dd-1b6c-968525494517"),
]


def matches(now: datetime | None = None) -> list[Match]:
    start = int((now or datetime.now(UTC)).timestamp() * 1000)
    result = []
    for i in range(100):
        win = i % 5 in {0, 1, 3}
        rounds = 18 + i % 7
        agent, agent_id = AGENTS[i % 5]
        result.append(Match(
            id=f"demo-{i}", started_at=start - i * 5_400_000, season_id="demo-act",
            map=["Ascent", "Haven", "Lotus", "Bind", "Sunset"][i % 5], agent=agent, agent_id=agent_id,
            outcome="win" if win else "loss", kills=21 + i % 6 if win else 13 + i % 5,
            deaths=12 + i % 7, assists=4 + i % 6, rounds=rounds,
            score=(258 if win else 198) * rounds, rating_delta=18 + i % 8 if win else -(15 + i % 6),
        ))
    return result
