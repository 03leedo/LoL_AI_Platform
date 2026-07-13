from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.summoner import Summoner
from app.schemas.riot import SummonerProfileResponse

SOLO_QUEUE_TYPE = "RANKED_SOLO_5x5"


def extract_solo_entry(league_entries: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    for entry in league_entries or []:
        if entry.get("queueType") == SOLO_QUEUE_TYPE:
            return entry
    return None


async def upsert_summoner(
    db: AsyncSession,
    account: dict,
    summoner: dict,
    platform_routing: str,
    league_entries: list[dict[str, Any]] | None = None,
) -> SummonerProfileResponse:
    solo = extract_solo_entry(league_entries)

    profile = Summoner(
        puuid=account["puuid"],
        game_name=account.get("gameName", ""),
        tag_line=account.get("tagLine", ""),
        platform_routing=platform_routing,
        summoner_id=summoner.get("id"),
        account_id=summoner.get("accountId"),
        profile_icon_id=summoner.get("profileIconId"),
        summoner_level=summoner.get("summonerLevel"),
        solo_tier=(solo or {}).get("tier"),
        solo_division=(solo or {}).get("rank"),
        solo_lp=(solo or {}).get("leaguePoints"),
        solo_wins=(solo or {}).get("wins"),
        solo_losses=(solo or {}).get("losses"),
    )

    merged = await db.merge(profile)
    await db.commit()
    await db.refresh(merged)

    return SummonerProfileResponse(
        puuid=merged.puuid,
        game_name=merged.game_name,
        tag_line=merged.tag_line,
        platform_routing=merged.platform_routing,
        summoner_id=merged.summoner_id,
        account_id=merged.account_id,
        profile_icon_id=merged.profile_icon_id,
        summoner_level=merged.summoner_level,
        solo_tier=merged.solo_tier,
        solo_division=merged.solo_division,
        solo_lp=merged.solo_lp,
        solo_wins=merged.solo_wins,
        solo_losses=merged.solo_losses,
    )
