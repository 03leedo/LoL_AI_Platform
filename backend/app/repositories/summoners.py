from sqlalchemy.ext.asyncio import AsyncSession

from app.models.summoner import Summoner
from app.schemas.riot import SummonerProfileResponse


async def upsert_summoner(
    db: AsyncSession,
    account: dict,
    summoner: dict,
    platform_routing: str,
) -> SummonerProfileResponse:
    profile = Summoner(
        puuid=account["puuid"],
        game_name=account.get("gameName", ""),
        tag_line=account.get("tagLine", ""),
        platform_routing=platform_routing,
        summoner_id=summoner.get("id"),
        account_id=summoner.get("accountId"),
        profile_icon_id=summoner.get("profileIconId"),
        summoner_level=summoner.get("summonerLevel"),
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
    )
