from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class RiotApiError(Exception):
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RiotClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.riot_api_key
        self.platform_routing = settings.riot_platform_routing
        self.regional_routing = settings.riot_regional_routing

    async def get_account_by_riot_id(self, game_name: str, tag_line: str) -> dict[str, Any]:
        encoded_game_name = quote(game_name, safe="")
        encoded_tag_line = quote(tag_line, safe="")
        path = f"/riot/account/v1/accounts/by-riot-id/{encoded_game_name}/{encoded_tag_line}"
        return await self._get(self.regional_routing, path)

    async def get_summoner_by_puuid(self, puuid: str) -> dict[str, Any]:
        encoded_puuid = quote(puuid, safe="")
        path = f"/lol/summoner/v4/summoners/by-puuid/{encoded_puuid}"
        return await self._get(self.platform_routing, path)

    async def get_match_ids(self, puuid: str, count: int = 10) -> list[str]:
        encoded_puuid = quote(puuid, safe="")
        path = f"/lol/match/v5/matches/by-puuid/{encoded_puuid}/ids"
        data = await self._get(self.regional_routing, path, params={"start": 0, "count": count})
        if not isinstance(data, list):
            raise RiotApiError("Unexpected Riot API response for match ids", 502)
        return data

    async def get_match(self, match_id: str) -> dict[str, Any]:
        encoded_match_id = quote(match_id, safe="")
        path = f"/lol/match/v5/matches/{encoded_match_id}"
        return await self._get(self.regional_routing, path)

    async def get_match_timeline(self, match_id: str) -> dict[str, Any]:
        encoded_match_id = quote(match_id, safe="")
        path = f"/lol/match/v5/matches/{encoded_match_id}/timeline"
        return await self._get(self.regional_routing, path)

    async def _get(
        self,
        routing: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if not self.api_key:
            raise RiotApiError("RIOT_API_KEY is not configured", 0)

        url = f"https://{routing}.api.riotgames.com{path}"
        headers = {"X-Riot-Token": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.get(url, headers=headers, params=params)
        except httpx.HTTPError as exc:
            raise RiotApiError(f"Riot API request failed: {exc}", 0) from exc

        if response.status_code >= 400:
            raise RiotApiError(
                message=self._error_message(response),
                status_code=response.status_code,
            )

        return response.json()

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"Riot API returned HTTP {response.status_code}"

        status = payload.get("status", {})
        message = status.get("message") or payload.get("message")
        if message:
            return f"Riot API returned HTTP {response.status_code}: {message}"
        return f"Riot API returned HTTP {response.status_code}"
