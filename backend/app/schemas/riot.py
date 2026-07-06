from pydantic import BaseModel, ConfigDict


class AccountResponse(BaseModel):
    puuid: str
    game_name: str
    tag_line: str


class SummonerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    puuid: str
    game_name: str
    tag_line: str
    platform_routing: str
    summoner_id: str | None = None
    account_id: str | None = None
    profile_icon_id: int | None = None
    summoner_level: int | None = None


class SummonerLookupResponse(BaseModel):
    account: AccountResponse
    summoner: SummonerProfileResponse


class MatchIdsResponse(BaseModel):
    puuid: str
    match_ids: list[str]


class TimelineFrameFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: str
    minute: int
    timestamp_ms: int

    blue_gold: int
    red_gold: int
    gold_diff: int

    blue_xp: int
    red_xp: int
    xp_diff: int

    blue_cs: int
    red_cs: int
    cs_diff: int

    blue_tower_kills: int
    red_tower_kills: int
    blue_dragon_kills: int
    red_dragon_kills: int
    blue_herald_kills: int
    red_herald_kills: int
    blue_baron_kills: int
    red_baron_kills: int


class MatchTimelineAnalysisResponse(BaseModel):
    match_id: str
    frame_count: int
    frames: list[TimelineFrameFeatureResponse]
