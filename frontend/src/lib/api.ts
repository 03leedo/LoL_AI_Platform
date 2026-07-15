const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

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
    solo_tier: string | null;
    solo_division: string | null;
    solo_lp: number | null;
    solo_wins: number | null;
    solo_losses: number | null;
  };
};

export type MatchIdsResponse = {
  puuid: string;
  match_ids: string[];
};

export type MatchSummary = {
  match_id: string;
  queue_id: number | null;
  game_creation: number | null;
  game_duration: number | null;
  champion_name: string | null;
  team_position: string | null;
  win: boolean | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  total_minions_killed: number | null;
  neutral_minions_killed: number | null;
  vision_score: number | null;
  total_damage_dealt_to_champions: number | null;
  total_damage_taken: number | null;
  gold_earned: number | null;
  kill_participation: number | null;
};

export type SummonerMatchHistoryResponse = {
  account: {
    puuid: string;
    game_name: string;
    tag_line: string;
  };
  matches: MatchSummary[];
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

export type WinCurvePoint = {
  minute: number;
  timestamp_ms: number;
  blue_win_prob: number;
};

export type MatchTimelineAnalysisResponse = {
  match_id: string;
  frame_count: number;
  frames: TimelineFrameFeature[];
  win_curve?: WinCurvePoint[];
};

export type ScoreConfidence = "low" | "medium" | "high";

export type ScoreDirection = "higher_is_better" | "higher_is_worse";

export type ScoreGroup = "performance" | "risk_style";

export type PlayerAnalysisScore = {
  value: number | null;
  confidence: ScoreConfidence;
  direction: ScoreDirection;
  group?: ScoreGroup;
};

export type TeamSide = "blue" | "red" | "neutral";

export type EvidenceContextSummary = {
  ally_deaths: number;
  enemy_deaths: number;
  ally_ward_events: number;
  enemy_ward_events: number;
  objective_events: number;
};

export type EvidenceContextParticipant = {
  participant_id: number;
  team: TeamSide;
  champion_name: string | null;
  is_player: boolean;
  x: number | null;
  y: number | null;
};

export type ObjectiveState = {
  blue_dragons: number;
  red_dragons: number;
  blue_heralds: number;
  red_heralds: number;
  blue_barons: number;
  red_barons: number;
  blue_towers: number;
  red_towers: number;
  blue_inhibitors: number;
  red_inhibitors: number;
  blue_voidgrubs: number;
  red_voidgrubs: number;
  blue_atakhans: number;
  red_atakhans: number;
};

export type EvidenceContextEvent = {
  timestamp_ms: number;
  minute: number;
  type: string;
  title: string;
  description: string;
  team: TeamSide;
  victim_team: TeamSide | null;
  ward_type: string | null;
  position_x: number | null;
  position_y: number | null;
  position_source: "event" | "participant_frame" | "objective_spawn" | "unknown";
  participant_ids: number[];
};

export type EvidenceContextSnapshot = {
  timestamp_ms: number;
  minute: number;
  offset_seconds: number;
  participants: EvidenceContextParticipant[];
  ward_events: EvidenceContextEvent[];
  objective_state: ObjectiveState;
};

export type EvidenceContext = {
  evidence_index: number;
  anchor_timestamp_ms: number;
  window_start_ms: number;
  window_end_ms: number;
  summary: EvidenceContextSummary;
  insights: Array<{
    tone: "risk" | "positive" | "info";
    title: string;
    description: string;
    source: "rules" | "llm";
  }>;
  snapshots: EvidenceContextSnapshot[];
  events: EvidenceContextEvent[];
};

export type PlayerAnalysisEvidence = {
  id?: string;
  minute: number;
  type: string;
  title: string;
  description: string;
  confidence: ScoreConfidence;
  context: EvidenceContext | null;
};

export type AnalysisStatementKind = "observation" | "hypothesis" | "limitation" | "replay_question";

export type AnalysisStatement = {
  kind: AnalysisStatementKind;
  text: string;
  evidence_ids: string[];
  confidence: ScoreConfidence;
};

export type MatchPlayerAnalysisResponse = {
  match_id: string;
  player: {
    puuid: string;
    champion: string | null;
    role: string | null;
    team: "blue" | "red";
    win: boolean | null;
  };
  scores: {
    death_cost_index: PlayerAnalysisScore;
    throw_index: PlayerAnalysisScore;
    objective_setup_score: PlayerAnalysisScore;
    lead_conversion_score: PlayerAnalysisScore;
    stability_score: PlayerAnalysisScore;
    gold_retention_score?: PlayerAnalysisScore | null;
    gambler_index?: PlayerAnalysisScore | null;
    teamfight_persistence_score?: PlayerAnalysisScore | null;
    death_acceleration_index?: PlayerAnalysisScore | null;
  };
  evidence: PlayerAnalysisEvidence[];
  statements?: AnalysisStatement[];
};

export type MatchKeyEventParticipant = {
  participant_id: number;
  team: TeamSide;
  champion_name: string | null;
  is_player: boolean;
  is_actor: boolean;
  x: number | null;
  y: number | null;
};

export type MatchKeyEvent = {
  minute: number;
  timestamp_ms: number;
  type: string;
  title: string;
  description: string;
  team: TeamSide;
  position_x: number | null;
  position_y: number | null;
  participants: MatchKeyEventParticipant[];
};

export type MatchReviewAssets = {
  data_dragon_version: string | null;
  map_id: number;
};

export type MatchTurningPoint = {
  minute: number;
  prob_before: number;
  prob_after: number;
  delta: number;
  event_type: string | null;
  title: string | null;
  description: string | null;
};

export type MatchReviewResponse = {
  timeline: MatchTimelineAnalysisResponse;
  analysis: MatchPlayerAnalysisResponse;
  key_events: MatchKeyEvent[];
  assets: MatchReviewAssets;
  turning_points?: MatchTurningPoint[];
};

export type HeatmapPoint = {
  match_id: string;
  minute: number;
  x: number;
  y: number;
  side: "blue" | "red";
  zone: string;
};

export type HeatmapZone = {
  zone: string;
  count: number;
  share: number;
  is_death_zone?: boolean;
};

export type SummonerHeatmapResponse = {
  puuid: string;
  matches_requested: number;
  matches_analyzed: number;
  kills: HeatmapPoint[];
  deaths: HeatmapPoint[];
  kill_zones: HeatmapZone[];
  death_zones: HeatmapZone[];
};

export type IngestJobState = "queued" | "running" | "done" | "failed";

export type IngestJob = {
  id: number;
  puuid: string;
  job_type: string;
  requested_count: number;
  state: IngestJobState;
  progress: number;
  error: string | null;
};

export type RankRole = "TOP" | "JUNGLE" | "MIDDLE" | "BOTTOM" | "UTILITY";

export type RankAbilityScore = {
  value: number | null;
  confidence: ScoreConfidence;
  direction: string;
};

export type RankScorecard = {
  games: number;
  abilities: Record<string, RankAbilityScore>;
};

export type RankRoleFit = {
  role: RankRole;
  games: number;
  win_rate: number | null;
  fit_score: number | null;
  confidence: ScoreConfidence;
};

export type RankAnalysisResponse = {
  puuid: string;
  window: string;
  games_analyzed: number;
  needs_ingest: boolean;
  scorecard: RankScorecard;
  roles: RankRoleFit[];
  recommended: string[];
  caution: string | null;
};

export type PlayerReportSeverity = "positive" | "warn" | "critical";

export type PlayerReportPattern = {
  key: string;
  severity: PlayerReportSeverity;
  title: string;
  description: string;
  stat: string | null;
  matches: string[];
};

export type PlayerReportAutopsy = {
  matches: number;
  deaths: number;
  kills: number;
  shutdown_deaths: number;
  shutdown_gold_conceded: number;
  /** 오브젝트가 살아 있거나 곧 생성될 시점의 데스 수 (동반률의 분모) */
  objective_analyzable_deaths: number;
  objective_linked_deaths: number;
  objective_linked_share: number;
  avg_first_death_minute: number | null;
};

export type PlayerReportResponse = {
  puuid: string;
  window: string;
  games_analyzed: number;
  needs_ingest: boolean;
  generated_by: "rules" | "llm";
  cached: boolean;
  cache_key: string;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  patterns: PlayerReportPattern[];
  autopsy: PlayerReportAutopsy | null;
  limitations?: string[];
  replay_questions?: string[];
};

export type ProfileRole = "TOP" | "JUNGLE" | "MIDDLE" | "BOTTOM" | "UTILITY" | "UNKNOWN";

export type ProfileDimensionKey =
  | "early_growth"
  | "resource_conversion"
  | "risk_management"
  | "objective_readiness"
  | "fight_contribution";

export type ProfileSubmetric = {
  key: string;
  label: string;
  value: number | null;
  percentile: number | null;
  lower_is_better: boolean;
};

export type ProfileDimension = {
  key: ProfileDimensionKey;
  label: string;
  score: number | null;
  raw_score: number | null;
  percentile: number | null;
  sample_size: number;
  confidence: ScoreConfidence;
  comparison_group: string;
  direction_group: string;
  submetrics: ProfileSubmetric[];
  evidence_match_ids: string[];
  insufficient_data: boolean;
};

export type PlayerProfileResponse = {
  puuid: string;
  role: ProfileRole;
  games: number;
  window: string;
  profile_version: number;
  comparison_group: string;
  insufficient_data: boolean;
  available_roles: string[];
  dimensions: ProfileDimension[];
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

export async function getSummonerMatchHistory({
  gameName,
  tagLine,
  count = 5
}: {
  gameName: string;
  tagLine: string;
  count?: number;
}): Promise<SummonerMatchHistoryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}/match-history?count=${count}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Match history lookup failed"));
  }

  return response.json();
}

export async function getSummonerHeatmap(
  gameName: string,
  tagLine: string,
  count = 10
): Promise<SummonerHeatmapResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}/heatmap?count=${count}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Kill/death heatmap analysis failed"));
  }

  return response.json();
}

export async function startSummonerIngest(
  gameName: string,
  tagLine: string,
  count = 20
): Promise<IngestJob> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}/ingest?count=${count}&queue=420`,
    {
      method: "POST",
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Match ingest request failed"));
  }

  return response.json();
}

export async function getIngestJob(id: number): Promise<IngestJob> {
  const response = await fetch(`${API_BASE_URL}/api/v1/riot/ingest-jobs/${id}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Ingest job lookup failed"));
  }

  return response.json();
}

export async function getRankAnalysis(
  gameName: string,
  tagLine: string,
  window = 20
): Promise<RankAnalysisResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}/rank-analysis?window=${window}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Rank analysis failed"));
  }

  return response.json();
}

export async function getPlayerReport(
  gameName: string,
  tagLine: string,
  window = 20,
  force = false
): Promise<PlayerReportResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}/report?window=${window}&force=${force}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Player report generation failed"));
  }

  return response.json();
}

export async function getPlayerProfile(
  gameName: string,
  tagLine: string,
  window = 20,
  role?: string
): Promise<PlayerProfileResponse> {
  const roleParam = role === undefined ? "" : `&role=${encodeURIComponent(role)}`;
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}/profile?window=${window}${roleParam}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Performance profile lookup failed"));
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

export async function getMatchReview({
  matchId,
  puuid
}: {
  matchId: string;
  puuid: string;
}): Promise<MatchReviewResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/matches/${encodeURIComponent(matchId)}/review?puuid=${encodeURIComponent(puuid)}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Match review failed"));
  }

  return response.json();
}

export async function getMatchPlayerAnalysis({
  matchId,
  puuid
}: {
  matchId: string;
  puuid: string;
}): Promise<MatchPlayerAnalysisResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/riot/matches/${encodeURIComponent(matchId)}/analysis?puuid=${encodeURIComponent(puuid)}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Player analysis failed"));
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
