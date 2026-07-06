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
