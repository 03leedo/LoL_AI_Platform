from typing import Literal

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
    solo_tier: str | None = None
    solo_division: str | None = None
    solo_lp: int | None = None
    solo_wins: int | None = None
    solo_losses: int | None = None


class SummonerLookupResponse(BaseModel):
    account: AccountResponse
    summoner: SummonerProfileResponse


class MatchIdsResponse(BaseModel):
    puuid: str
    match_ids: list[str]


class MatchSummaryResponse(BaseModel):
    match_id: str
    queue_id: int | None = None
    game_creation: int | None = None
    game_duration: int | None = None
    champion_name: str | None = None
    team_position: str | None = None
    win: bool | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    total_minions_killed: int | None = None
    neutral_minions_killed: int | None = None
    vision_score: int | None = None
    total_damage_dealt_to_champions: int | None = None
    total_damage_taken: int | None = None
    gold_earned: int | None = None
    kill_participation: int | None = None


class SummonerMatchHistoryResponse(BaseModel):
    account: AccountResponse
    matches: list[MatchSummaryResponse]


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
    win_curve: list["WinCurvePointResponse"] = []


class WinCurvePointResponse(BaseModel):
    minute: int
    timestamp_ms: int
    blue_win_prob: float


class PlayerAnalysisPlayerResponse(BaseModel):
    puuid: str
    champion: str | None
    role: str | None
    team: Literal["blue", "red"]
    win: bool | None


class PlayerAnalysisScoreResponse(BaseModel):
    value: int | None
    confidence: Literal["low", "medium", "high"]
    direction: Literal["higher_is_better", "higher_is_worse"]
    # performance: 높을수록 긍정적 능력 / risk_style: 높을수록 강한 경향(성향·위험 신호)
    group: Literal["performance", "risk_style"] = "performance"


class PlayerAnalysisScoresResponse(BaseModel):
    death_cost_index: PlayerAnalysisScoreResponse
    throw_index: PlayerAnalysisScoreResponse
    objective_setup_score: PlayerAnalysisScoreResponse
    lead_conversion_score: PlayerAnalysisScoreResponse
    stability_score: PlayerAnalysisScoreResponse
    gold_retention_score: PlayerAnalysisScoreResponse | None = None
    gambler_index: PlayerAnalysisScoreResponse | None = None
    teamfight_persistence_score: PlayerAnalysisScoreResponse | None = None
    death_acceleration_index: PlayerAnalysisScoreResponse | None = None


class EvidenceContextSummaryResponse(BaseModel):
    ally_deaths: int = 0
    enemy_deaths: int = 0
    ally_ward_events: int = 0
    enemy_ward_events: int = 0
    objective_events: int = 0


class EvidenceContextParticipantResponse(BaseModel):
    participant_id: int
    team: Literal["blue", "red", "neutral"]
    champion_name: str | None = None
    is_player: bool = False
    x: int | None = None
    y: int | None = None


class ObjectiveStateResponse(BaseModel):
    blue_dragons: int = 0
    red_dragons: int = 0
    blue_heralds: int = 0
    red_heralds: int = 0
    blue_barons: int = 0
    red_barons: int = 0
    blue_towers: int = 0
    red_towers: int = 0
    blue_inhibitors: int = 0
    red_inhibitors: int = 0
    blue_voidgrubs: int = 0
    red_voidgrubs: int = 0
    blue_atakhans: int = 0
    red_atakhans: int = 0


class EvidenceContextEventResponse(BaseModel):
    timestamp_ms: int
    minute: int
    type: str
    title: str
    description: str
    team: Literal["blue", "red", "neutral"]
    victim_team: Literal["blue", "red", "neutral"] | None = None
    ward_type: str | None = None
    position_x: int | None = None
    position_y: int | None = None
    position_source: Literal["event", "participant_frame", "objective_spawn", "unknown"]
    participant_ids: list[int]


class EvidenceContextSnapshotResponse(BaseModel):
    timestamp_ms: int
    minute: int
    offset_seconds: int
    participants: list[EvidenceContextParticipantResponse]
    ward_events: list[EvidenceContextEventResponse]
    objective_state: ObjectiveStateResponse


class EvidenceContextInsightResponse(BaseModel):
    tone: Literal["risk", "positive", "info"]
    title: str
    description: str
    source: Literal["rules", "llm"] = "rules"


class EvidenceContextResponse(BaseModel):
    evidence_index: int
    anchor_timestamp_ms: int
    window_start_ms: int
    window_end_ms: int
    summary: EvidenceContextSummaryResponse
    insights: list[EvidenceContextInsightResponse]
    snapshots: list[EvidenceContextSnapshotResponse]
    events: list[EvidenceContextEventResponse]


class PlayerAnalysisEvidenceResponse(BaseModel):
    id: str | None = None
    minute: int
    type: str
    title: str
    description: str
    confidence: Literal["low", "medium", "high"]
    context: EvidenceContextResponse | None = None


class AnalysisStatementResponse(BaseModel):
    kind: Literal["observation", "hypothesis", "limitation", "replay_question"]
    text: str
    evidence_ids: list[str] = []
    confidence: Literal["low", "medium", "high"] = "medium"


class MatchPlayerAnalysisResponse(BaseModel):
    match_id: str
    player: PlayerAnalysisPlayerResponse
    scores: PlayerAnalysisScoresResponse
    evidence: list[PlayerAnalysisEvidenceResponse]
    statements: list[AnalysisStatementResponse] = []


class KeyEventParticipantResponse(BaseModel):
    participant_id: int
    team: Literal["blue", "red", "neutral"]
    champion_name: str | None = None
    is_player: bool = False
    is_actor: bool = False
    x: int | None = None
    y: int | None = None


class MatchKeyEventResponse(BaseModel):
    minute: int
    timestamp_ms: int
    type: str
    title: str
    description: str
    team: Literal["blue", "red", "neutral"]
    position_x: int | None = None
    position_y: int | None = None
    participants: list[KeyEventParticipantResponse]


class MatchReviewAssetsResponse(BaseModel):
    data_dragon_version: str | None = None
    map_id: int = 11


class TurningPointResponse(BaseModel):
    minute: int
    prob_before: float
    prob_after: float
    delta: float
    event_type: str | None = None
    title: str | None = None
    description: str | None = None


class MatchReviewResponse(BaseModel):
    timeline: MatchTimelineAnalysisResponse
    analysis: MatchPlayerAnalysisResponse
    key_events: list[MatchKeyEventResponse]
    assets: MatchReviewAssetsResponse
    turning_points: list[TurningPointResponse] = []


class HeatmapPointResponse(BaseModel):
    match_id: str
    minute: int
    x: int
    y: int
    side: Literal["blue", "red"]
    zone: str


class HeatmapZoneResponse(BaseModel):
    zone: str
    count: int
    share: float
    is_death_zone: bool = False


class SummonerHeatmapResponse(BaseModel):
    puuid: str
    matches_requested: int
    matches_analyzed: int
    kills: list[HeatmapPointResponse]
    deaths: list[HeatmapPointResponse]
    kill_zones: list[HeatmapZoneResponse]
    death_zones: list[HeatmapZoneResponse]


class IngestJobResponse(BaseModel):
    id: int
    puuid: str
    job_type: str
    requested_count: int
    state: str
    progress: int
    error: str | None = None


class AbilityScoreResponse(BaseModel):
    value: int | None = None
    confidence: Literal["low", "medium", "high"] = "low"
    direction: str = "higher_is_better"


class ScorecardResponse(BaseModel):
    games: int
    abilities: dict[str, AbilityScoreResponse]


class RoleFitResponse(BaseModel):
    role: str
    games: int
    win_rate: float | None = None
    fit_score: int | None = None
    confidence: Literal["low", "medium", "high"] = "low"


class RankAnalysisResponse(BaseModel):
    puuid: str
    window: str
    games_analyzed: int
    needs_ingest: bool
    scorecard: ScorecardResponse
    roles: list[RoleFitResponse]
    recommended: list[str]
    caution: str | None = None


class ProfileSubmetricResponse(BaseModel):
    key: str
    label: str
    value: float | None = None
    percentile: int | None = None
    lower_is_better: bool = False


class ProfileDimensionResponse(BaseModel):
    key: str
    label: str
    score: int | None = None
    raw_score: int | None = None
    percentile: int | None = None
    sample_size: int = 0
    effective_sample_size: float = 0.0
    confidence: Literal["low", "medium", "high"] = "low"
    comparison_group: str
    direction_group: str = "performance"
    submetrics: list[ProfileSubmetricResponse] = []
    evidence_match_ids: list[str] = []
    insufficient_data: bool = False


class PlayerProfileResponse(BaseModel):
    puuid: str
    role: str
    games: int
    window: str
    profile_version: int
    comparison_group: str
    computed_at_ms: int | None = None
    insufficient_data: bool
    available_roles: list[str] = []
    dimensions: list[ProfileDimensionResponse] = []


class SelectionDriverResponse(BaseModel):
    key: str
    label: str
    value: float
    profile_value: float
    diff: float


class MatchSelectionResponse(BaseModel):
    kind: Literal["representative", "best", "deviation"]
    match_id: str
    champion_name: str | None = None
    win: bool | None = None
    game_creation: int | None = None
    distance: float
    mean_value: float
    dimensions_used: int = 0
    reason: str
    drivers: list[SelectionDriverResponse] = []
    vector: dict[str, float | None] = {}


class MatchSelectionsResponse(BaseModel):
    puuid: str
    role: str
    window: str
    games_considered: int
    eligible_matches: int
    excluded_matches: int
    selection_version: int
    method: str
    computed_at_ms: int | None = None
    insufficient_data: bool
    profile_vector: dict[str, float] = {}
    profile_vector_basis: str | None = None
    representative: MatchSelectionResponse | None = None
    best: MatchSelectionResponse | None = None
    deviation: MatchSelectionResponse | None = None


class ReportPatternResponse(BaseModel):
    key: str
    severity: Literal["positive", "warn", "critical"]
    title: str
    description: str
    stat: str | None = None
    matches: list[str] = []


class DeathAutopsyResponse(BaseModel):
    matches: int = 0
    deaths: int = 0
    kills: int = 0
    shutdown_deaths: int = 0
    shutdown_gold_conceded: int = 0
    # Denominator-corrected (Phase 3): deaths while an elite objective was
    # live or imminent; share is linked/analyzable, not linked/all.
    objective_analyzable_deaths: int = 0
    objective_linked_deaths: int = 0
    objective_linked_share: float = 0.0
    avg_first_death_minute: float | None = None


class ReportStatementResponse(BaseModel):
    text: str
    refs: list[str] = []


class PlayerReportResponse(BaseModel):
    puuid: str
    window: str
    games_analyzed: int
    needs_ingest: bool
    generated_by: Literal["rules", "llm"]
    cached: bool = False
    cache_key: str = ""
    summary: str
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []
    # Phase 6: evidence-grounded LLM statements (refs point at pattern ids /
    # match ids present in the report payload; enforced server-side).
    observations: list[ReportStatementResponse] = []
    hypotheses: list[ReportStatementResponse] = []
    llm_prompt_version: int | None = None
    llm_insufficient_reason: str | None = None
    limitations: list[str] = []
    replay_questions: list[str] = []
    patterns: list[ReportPatternResponse] = []
    autopsy: DeathAutopsyResponse | None = None
