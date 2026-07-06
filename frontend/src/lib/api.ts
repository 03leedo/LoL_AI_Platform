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

export type MatchIdsResponse = {
  puuid: string;
  match_ids: string[];
};

export type TimelineFrameFeature = {
  match_id: string;
  minute: number;
  timestamp_ms: number;
  blue_gold: number;
  red_gold: number;
  gold_diff: number;
  blue_xp: number;
  red_xp: number;
  xp_diff: number;
  blue_cs: number;
  red_cs: number;
  cs_diff: number;
  blue_tower_kills: number;
  red_tower_kills: number;
  blue_dragon_kills: number;
  red_dragon_kills: number;
  blue_herald_kills: number;
  red_herald_kills: number;
  blue_baron_kills: number;
  red_baron_kills: number;
};

export type MatchTimelineAnalysisResponse = {
  match_id: string;
  frame_count: number;
  frames: TimelineFrameFeature[];
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

export async function getRecentMatchIds({
  gameName,
  tagLine,
  count = 5
}: {
  gameName: string;
  tagLine: string;
  count?: number;
}): Promise<MatchIdsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}/matches?count=${count}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Recent matches lookup failed"));
  }

  return response.json();
}

export async function getMatchTimelineAnalysis(matchId: string): Promise<MatchTimelineAnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/riot/matches/${encodeURIComponent(matchId)}/timeline`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Timeline analysis failed"));
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
    throw new Error(await errorMessage(response, "Summoner lookup failed"));
  }

  return response.json();
}

async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    return `${fallback} with HTTP ${response.status}`;
  }

  return fallback;
}
