const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type SystemHealth = {
  status: string;
  service: string;
  environment: string;
  database: string;
  riot_api: string;
};

export type SummonerLookupResponse = {
  account: {
    puuid: string;
    game_name: string;
    tag_line: string;
  };
  summoner: {
    puuid: string;
    game_name: string;
    tag_line: string;
    platform_routing: string;
    summoner_id: string | null;
    account_id: string | null;
    profile_icon_id: number | null;
    summoner_level: number | null;
  };
};

export async function getHealth(): Promise<SystemHealth> {
  const response = await fetch(`${API_BASE_URL}/api/v1/health`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error("Backend health check failed");
  }

  return response.json();
}

export async function searchSummoner({
  gameName,
  tagLine
}: {
  gameName: string;
  tagLine: string;
}): Promise<SummonerLookupResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    let message = "Summoner lookup failed";
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      message = `Summoner lookup failed with HTTP ${response.status}`;
    }
    throw new Error(message);
  }

  return response.json();
}
