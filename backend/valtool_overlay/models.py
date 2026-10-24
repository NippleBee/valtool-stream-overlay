"""Public JSON models. Camel-case aliases keep existing settings/cache files readable."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator
from pydantic.alias_generators import to_camel

METRICS = {
    "kd", "kda", "kdaRatio", "acs", "winrate", "winsLosses",
    "rrGain", "rrLoss", "rrNet", "lastDelta", "leaderboard",
}


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)

    def json_data(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)


class Settings(Model):
    layout: Literal["large", "compact", "mini"] = "compact"
    theme: Literal["midnight", "pastel"] = "midnight"
    accent: str = "#c4b5fd"
    background: str = "#14151f"
    text_color: str = "#f5f5fa"
    opacity: float = Field(default=0.94, ge=0, le=1, allow_inf_nan=False)
    radius: StrictInt = Field(default=18, ge=0, le=36)
    glow: StrictInt = Field(default=25, ge=0, le=60)
    title: str = Field(default="CURRENT RANK", max_length=40)
    metrics: tuple[str, ...] = ("kd", "winsLosses", "winrate")
    match_count: StrictInt | None = Field(default=20, ge=1, le=100_000)
    scope: Literal["available", "act"] = "available"
    show_matches: StrictBool = True
    recent_count: StrictInt = Field(default=5, ge=1, le=10)
    show_last_delta: StrictBool = True
    hide_when_offline: StrictBool = False

    @field_validator("accent", "background", "text_color")
    @classmethod
    def color(cls, value: str) -> str:
        if len(value) != 7 or value[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in value[1:]):
            raise ValueError("Color must use the #RRGGBB format")
        return value

    @field_validator("title")
    @classmethod
    def title_text(cls, value: str) -> str:
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Title must not contain control characters")
        return value

    @model_validator(mode="after")
    def slots(self):
        limit = {"large": 6, "compact": 3, "mini": 1}[self.layout]
        if not 1 <= len(self.metrics) <= limit or len(set(self.metrics)) != len(self.metrics) or not set(self.metrics) <= METRICS:
            raise ValueError(f"Choose between 1 and {limit} distinct metrics")
        return self


class Match(Model):
    id: str
    started_at: int
    season_id: str
    queue: str = "competitive"
    map: str
    agent: str
    outcome: Literal["win", "loss", "draw", "unknown"]
    kills: int = Field(ge=0)
    deaths: int = Field(ge=0)
    assists: int = Field(ge=0)
    score: int = Field(ge=0)
    rounds: int = Field(ge=0)
    rating_delta: int | None = None
    is_final: bool = True
    is_remake: bool = False
    agent_id: str | None = None


class Rank(Model):
    name: str
    tier: int
    rr: int | None = None
    leaderboard: int | None = None
    season_id: str | None = None
    season_name: str | None = None


class Stats(Model):
    games: int
    wins: int
    losses: int
    draws: int
    kills: int
    deaths: int
    assists: int
    kd: float | None
    kda_ratio: float | None
    acs: float | None
    winrate: float | None
    rr_gain: int | None
    rr_loss: int | None
    rr_net: int | None
    last_delta: int | None
    rr_covered: int
    requested: int | None
    available: int
    is_complete: bool


class Connection(Model):
    phase: str = "waiting"
    message: str = "Waiting for Riot Client"
    riot_client_available: bool = False
    valorant_running: bool = False
    authenticated: bool = False
    account: str | None = None
    loop_state: str | None = None
    updated_at: datetime | None = None
    error: str | None = None


class Snapshot(Model):
    revision: int
    settings: Settings
    connection: Connection
    rank: Rank | None
    stats: Stats
    recent_matches: list[Match]
    mode: Literal["live", "demo"]
    loaded: int
    total: int | None
    syncing: bool
    sync_error: str | None = None
