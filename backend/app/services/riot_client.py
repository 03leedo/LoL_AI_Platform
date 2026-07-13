import asyncio
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings
from app.services.rate_limiter import SlidingWindowRateLimiter, Sleeper, get_riot_rate_limiter


class RiotApiError(Exception):
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RiotClient:
    def __init__(
        self,
        limiter: SlidingWindowRateLimiter | None = None,
        sleeper: Sleeper | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = settings.riot_api_key
        self.platform_routing = settings.riot_platform_routing
        self.regional_routing = settings.riot_regional_routing
        self.max_attempts = max(1, settings.riot_request_max_attempts)
        self.retry_backoff_seconds = settings.riot_retry_backoff_seconds
        self._limiter = limiter if limiter is not None else get_riot_rate_limiter()
        self._sleep: Sleeper = sleeper if sleeper is not None else asyncio.sleep
        self._transport = transport

    async def get_account_by_riot_id(self, game_name: str, tag_line: str) -> dict[str, Any]:
        encoded_game_name = quote(game_name, safe="")
        encoded_tag_line = quote(tag_line, safe="")
        path = f"/riot/account/v1/accounts/by-riot-id/{encoded_game_name}/{encoded_tag_line}"
        return await self._get(self.regional_routing, path)

    async def get_summoner_by_puuid(self, puuid: str) -> dict[str, Any]:
        encoded_puuid = quote(puuid, safe="")
        path = f"/lol/summoner/v4/summoners/by-puuid/{encoded_puuid}"
        return await self._get(self.platform_routing, path)

    async def get_league_entries_by_puuid(self, puuid: str) -> list[dict[str, Any]]:
        encoded_puuid = quote(puuid, safe="")
        path = f"/lol/league/v4/entries/by-puuid/{encoded_puuid}"
        data = await self._get(self.platform_routing, path)
        if not isinstance(data, list):
            raise RiotApiError("Unexpected Riot API response for league entries", 502)
        return data

    async def get_match_ids(
        self,
        puuid: str,
        count: int = 10,
        queue: int | None = None,
        start: int = 0,
    ) -> list[str]:
        encoded_puuid = quote(puuid, safe="")
        path = f"/lol/match/v5/matches/by-puuid/{encoded_puuid}/ids"
        params: dict[str, Any] = {"start": start, "count": count}
        if queue is not None:
            params["queue"] = queue
        data = await self._get(self.regional_routing, path, params=params)
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
        last_error = RiotApiError("Riot API request failed", 0)

        for attempt in range(1, self.max_attempts + 1):
            await self._limiter.acquire()

            try:
                async with httpx.AsyncClient(timeout=12.0, transport=self._transport) as client:
                    response = await client.get(url, headers=headers, params=params)
            except httpx.HTTPError as exc:
                last_error = RiotApiError(f"Riot API request failed: {exc}", 0)
                if attempt < self.max_attempts:
                    await self._sleep(self._backoff_seconds(attempt))
                    continue
                raise last_error from exc

            if response.status_code == 429:
                last_error = RiotApiError(self._error_message(response), 429)
                if attempt < self.max_attempts:
                    await self._sleep(self._retry_after_seconds(response, attempt))
                    continue
                raise last_error

            if response.status_code >= 500:
                last_error = RiotApiError(self._error_message(response), response.status_code)
                if attempt < self.max_attempts:
                    await self._sleep(self._backoff_seconds(attempt))
                    continue
                raise last_error

            if response.status_code >= 400:
                raise RiotApiError(
                    message=self._error_message(response),
                    status_code=response.status_code,
                )

            return response.json()

        raise last_error

    def _retry_after_seconds(self, response: httpx.Response, attempt: int) -> float:
        raw = response.headers.get("Retry-After")
        if raw is not None:
            try:
                return max(0.0, float(raw))
            except ValueError:
                pass
        return self._backoff_seconds(attempt)

    def _backoff_seconds(self, attempt: int) -> float:
        return min(8.0, self.retry_backoff_seconds * (2 ** (attempt - 1)))

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
