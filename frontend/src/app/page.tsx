"use client";

import { BarChart3, ChevronRight, ListChecks, Loader2, Search, Swords } from "lucide-react";
import { FormEvent, ReactNode, useState } from "react";

import {
  getMatchReview,
  getSummonerMatchHistory,
  MatchPlayerAnalysisResponse,
  MatchSummary,
  MatchTimelineAnalysisResponse,
  PlayerAnalysisScore,
  searchSummoner,
  SummonerLookupResponse,
  TimelineFrameFeature
} from "@/lib/api";

type LoadState = "idle" | "loading" | "success" | "error";

const RECENT_MATCH_COUNT = 8;

export default function Home() {
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [lookupState, setLookupState] = useState<LoadState>("idle");
  const [lookup, setLookup] = useState<SummonerLookupResponse | null>(null);
  const [lookupError, setLookupError] = useState("");
  const [matchState, setMatchState] = useState<LoadState>("idle");
  const [matchHistory, setMatchHistory] = useState<MatchSummary[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState("");
  const [matchError, setMatchError] = useState("");
  const [reviewState, setReviewState] = useState<LoadState>("idle");
  const [timeline, setTimeline] = useState<MatchTimelineAnalysisResponse | null>(null);
  const [playerAnalysis, setPlayerAnalysis] = useState<MatchPlayerAnalysisResponse | null>(null);
  const [reviewError, setReviewError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedGameName = gameName.trim();
    const normalizedTagLine = tagLine.trim();

    setLookupState("loading");
    setLookupError("");
    setLookup(null);
    resetMatches();

    try {
      const data = await searchSummoner({
        gameName: normalizedGameName,
        tagLine: normalizedTagLine
      });
      setLookup(data);
      setLookupState("success");
    } catch (err) {
      setLookupError(err instanceof Error ? err.message : "소환사 검색에 실패했습니다.");
      setLookupState("error");
      return;
    }

    setMatchState("loading");
    try {
      const history = await getSummonerMatchHistory({
        gameName: normalizedGameName,
        tagLine: normalizedTagLine,
        count: RECENT_MATCH_COUNT
      });
      setMatchHistory(history.matches);
      setMatchState("success");
    } catch (err) {
      setMatchError(err instanceof Error ? err.message : "최근 전적을 불러오지 못했습니다.");
      setMatchState("error");
    }
  }

  async function onReviewMatch(matchId: string) {
    if (!lookup) {
      return;
    }

    setSelectedMatchId(matchId);
    setReviewState("loading");
    setReviewError("");
    setTimeline(null);
    setPlayerAnalysis(null);

    try {
      const review = await getMatchReview({
        matchId,
        puuid: lookup.account.puuid
      });
      setTimeline(review.timeline);
      setPlayerAnalysis(review.analysis);
      setReviewState("success");
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : "경기 분석에 실패했습니다.");
      setReviewState("error");
    }
  }

  function resetMatches() {
    setMatchState("idle");
    setMatchHistory([]);
    setSelectedMatchId("");
    setMatchError("");
    setReviewState("idle");
    setTimeline(null);
    setPlayerAnalysis(null);
    setReviewError("");
  }

  const latestFrame = timeline?.frames[timeline.frames.length - 1];

  return (
    <main className="app-shell">
      <section className="search-hero">
        <div className="hero-copy">
          <p className="eyebrow">LoL AI Platform</p>
          <h1>소환사 전적 분석</h1>
          <p>최근 경기 기록을 불러오고, 선택한 판의 흐름과 손해 포인트를 바로 복기합니다.</p>
        </div>

        <form className="summoner-search" onSubmit={onSubmit}>
          <div className="search-fields">
            <label htmlFor="gameName">Riot ID</label>
            <input
              id="gameName"
              name="gameName"
              value={gameName}
              onChange={(event) => setGameName(event.target.value)}
              placeholder="Hide on bush"
              autoComplete="off"
              required
            />
          </div>

          <div className="search-fields tag-field">
            <label htmlFor="tagLine">Tag</label>
            <input
              id="tagLine"
              name="tagLine"
              value={tagLine}
              onChange={(event) => setTagLine(event.target.value)}
              placeholder="KR1"
              autoComplete="off"
              required
            />
          </div>

          <button type="submit" disabled={lookupState === "loading"}>
            {lookupState === "loading" ? (
              <Loader2 className="spin" size={18} aria-hidden="true" />
            ) : (
              <Search size={18} aria-hidden="true" />
            )}
            <span>검색</span>
          </button>
        </form>

        {lookupState === "error" && <p className="error-copy hero-error">{lookupError}</p>}
      </section>

      {lookupState === "success" && lookup && (
        <section className="summoner-strip">
          <div>
            <span className="summoner-avatar">{lookup.account.game_name.slice(0, 1).toUpperCase()}</span>
          </div>
          <div className="summoner-info">
            <p>{lookup.account.game_name}#{lookup.account.tag_line}</p>
            <span>Level {lookup.summoner.summoner_level ?? "-"} · {lookup.summoner.platform_routing.toUpperCase()}</span>
          </div>
        </section>
      )}

      <section className="match-layout">
        <section className="history-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Match history</p>
              <h2>최근 전적</h2>
            </div>
            <Swords size={22} aria-hidden="true" />
          </div>

          {matchState === "idle" && <EmptyState label="소환사를 검색하면 최근 전적이 여기에 표시됩니다." />}
          {matchState === "loading" && <LoadingState label="최근 전적을 불러오는 중입니다." />}
          {matchState === "error" && <p className="error-copy">{matchError}</p>}
          {matchState === "success" && matchHistory.length === 0 && <EmptyState label="최근 경기 기록을 찾지 못했습니다." />}
          {matchState === "success" && matchHistory.length > 0 && (
            <div className="match-list">
              {matchHistory.map((match) => (
                <MatchCard
                  key={match.match_id}
                  match={match}
                  isSelected={selectedMatchId === match.match_id}
                  isLoading={reviewState === "loading" && selectedMatchId === match.match_id}
                  onReview={() => onReviewMatch(match.match_id)}
                />
              ))}
            </div>
          )}
        </section>

        <aside className="review-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Review</p>
              <h2>경기 분석</h2>
            </div>
            <ListChecks size={22} aria-hidden="true" />
          </div>

          {reviewState === "idle" && <EmptyState label="전적 카드에서 자세히 보기를 누르면 분석이 열립니다." />}
          {reviewState === "loading" && <LoadingState label="경기 흐름과 손해 포인트를 계산하는 중입니다." />}
          {reviewState === "error" && <p className="error-copy">{reviewError}</p>}
          {reviewState === "success" && playerAnalysis && timeline && (
            <div className="review-stack">
              <div className="review-summary">
                <div>
                  <span className={playerAnalysis.player.win ? "result-badge win" : "result-badge loss"}>
                    {playerAnalysis.player.win ? "Win" : "Loss"}
                  </span>
                  <h3>{playerAnalysis.player.champion ?? "Unknown champion"}</h3>
                  <p>{formatRole(playerAnalysis.player.role)} · {playerAnalysis.player.team}</p>
                </div>
              </div>

              <div className="score-grid">
                <ScoreCard label="Death Cost" score={playerAnalysis.scores.death_cost_index} />
                <ScoreCard label="Throw Index" score={playerAnalysis.scores.throw_index} />
                <ScoreCard label="Stability" score={playerAnalysis.scores.stability_score} />
                <ScoreCard label="Objective" score={playerAnalysis.scores.objective_setup_score} />
                <ScoreCard label="Lead Conversion" score={playerAnalysis.scores.lead_conversion_score} />
              </div>

              {latestFrame && (
                <div className="timeline-summary">
                  <MiniMetric label="Gold" value={formatDiff(latestFrame.gold_diff)} />
                  <MiniMetric label="XP" value={formatDiff(latestFrame.xp_diff)} />
                  <MiniMetric label="CS" value={formatDiff(latestFrame.cs_diff)} />
                </div>
              )}

              <TimelineChart frames={timeline.frames} />

              <div className="evidence-panel">
                <h3>주요 근거</h3>
                <div className="evidence-list">
                  {playerAnalysis.evidence.map((item, index) => (
                    <article className="evidence-item" key={`${item.type}-${item.minute}-${index}`}>
                      <div>
                        <span className="evidence-minute">{item.minute}m</span>
                        <strong>{item.title}</strong>
                      </div>
                      <p>{item.description}</p>
                      <ConfidencePill confidence={item.confidence} />
                    </article>
                  ))}
                </div>
              </div>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}

function MatchCard({
  match,
  isSelected,
  isLoading,
  onReview
}: {
  match: MatchSummary;
  isSelected: boolean;
  isLoading: boolean;
  onReview: () => void;
}) {
  const cs = (match.total_minions_killed ?? 0) + (match.neutral_minions_killed ?? 0);
  const kda = formatKda(match.kills, match.deaths, match.assists);
  const championName = match.champion_name ?? "Unknown";

  return (
    <article className={isSelected ? "match-card is-selected" : "match-card"}>
      <div className="champion-art">
        {match.champion_name && (
          <img
            src={championSplashUrl(match.champion_name)}
            alt=""
            loading="lazy"
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
        )}
      </div>

      <div className="match-content">
        <div className="match-topline">
          <span className={match.win === null ? "result-badge" : match.win ? "result-badge win" : "result-badge loss"}>
            {match.win === null ? "Result" : match.win ? "Win" : "Loss"}
          </span>
          <span>{queueLabel(match.queue_id)}</span>
          <span>{formatGameTime(match.game_creation)}</span>
        </div>

        <div className="match-mainline">
          <div>
            <h3>{championName}</h3>
            <p>{formatRole(match.team_position)} · {formatDuration(match.game_duration)}</p>
          </div>
          <div className="match-kda">
            <strong>{match.kills ?? 0} / {match.deaths ?? 0} / {match.assists ?? 0}</strong>
            <span>{kda}</span>
          </div>
        </div>

        <div className="match-card-stats">
          <span>CS {cs}</span>
          <span>CS/min {formatCsPerMinute(cs, match.game_duration)}</span>
          <span>Vision {match.vision_score ?? "-"}</span>
        </div>
      </div>

      <button type="button" onClick={onReview} disabled={isLoading}>
        {isLoading ? <Loader2 className="spin" size={18} aria-hidden="true" /> : <ChevronRight size={18} aria-hidden="true" />}
        <span>자세히 보기</span>
      </button>
    </article>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="empty-state">
      <Search size={28} aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-state">
      <Loader2 className="spin" size={24} aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

function ScoreCard({ label, score }: { label: string; score: PlayerAnalysisScore }) {
  return (
    <div className={score.direction === "higher_is_worse" ? "score-card is-risk" : "score-card"}>
      <span>{label}</span>
      <strong>{score.value === null ? "N/A" : score.value}</strong>
      <ConfidencePill confidence={score.confidence} />
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="mini-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ConfidencePill({ confidence }: { confidence: "low" | "medium" | "high" }) {
  return <span className={`confidence-pill ${confidence}`}>{confidence}</span>;
}

function TimelineChart({ frames }: { frames: TimelineFrameFeature[] }) {
  if (frames.length < 2) {
    return <div className="timeline-chart is-empty">No chart data</div>;
  }

  const width = 760;
  const height = 220;
  const padding = 28;
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;
  const diffs = frames.map((frame) => frame.gold_diff);
  const minDiff = Math.min(0, ...diffs);
  const maxDiff = Math.max(0, ...diffs);
  const range = maxDiff - minDiff || 1;
  const maxMinute = Math.max(1, ...frames.map((frame) => frame.minute));
  const zeroY = height - padding - ((0 - minDiff) / range) * chartHeight;

  const points = frames
    .map((frame) => {
      const x = padding + (frame.minute / maxMinute) * chartWidth;
      const y = height - padding - ((frame.gold_diff - minDiff) / range) * chartHeight;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <div className="timeline-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Gold difference over time">
        <line className="chart-zero" x1={padding} x2={width - padding} y1={zeroY} y2={zeroY} />
        <polyline className="chart-line" points={points} />
        <text x={padding} y={22}>
          Gold diff
        </text>
        <text x={width - padding} y={height - 8} textAnchor="end">
          {maxMinute}m
        </text>
      </svg>
    </div>
  );
}

function championSplashUrl(championName: string) {
  const assetName = championAssetName(championName);
  return `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${assetName}_0.jpg`;
}

function championAssetName(championName: string) {
  const overrides: Record<string, string> = {
    FiddleSticks: "Fiddlesticks"
  };
  return overrides[championName] ?? championName.replace(/[^A-Za-z0-9]/g, "");
}

function queueLabel(queueId: number | null) {
  const labels: Record<number, string> = {
    420: "솔로랭크",
    430: "일반",
    440: "자유랭크",
    450: "칼바람",
    490: "빠른대전"
  };
  return queueId ? labels[queueId] ?? `Queue ${queueId}` : "게임";
}

function formatRole(role: string | null) {
  const labels: Record<string, string> = {
    TOP: "탑",
    JUNGLE: "정글",
    MIDDLE: "미드",
    MID: "미드",
    BOTTOM: "원딜",
    ADC: "원딜",
    UTILITY: "서포터",
    SUPPORT: "서포터"
  };
  if (!role) {
    return "-";
  }
  return labels[role.toUpperCase()] ?? role;
}

function formatDuration(seconds: number | null) {
  if (!seconds) {
    return "-";
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}

function formatCsPerMinute(cs: number, seconds: number | null) {
  if (!seconds) {
    return "-";
  }
  return (cs / (seconds / 60)).toFixed(1);
}

function formatKda(kills: number | null, deaths: number | null, assists: number | null) {
  const deathCount = deaths ?? 0;
  if (deathCount === 0) {
    return "Perfect";
  }
  return `${(((kills ?? 0) + (assists ?? 0)) / deathCount).toFixed(2)} KDA`;
}

function formatGameTime(timestamp: number | null) {
  if (!timestamp) {
    return "-";
  }
  const date = new Date(timestamp);
  const diffMs = Date.now() - date.getTime();
  const diffHours = Math.floor(diffMs / 3_600_000);
  if (diffHours < 1) {
    return "방금 전";
  }
  if (diffHours < 24) {
    return `${diffHours}시간 전`;
  }
  return `${Math.floor(diffHours / 24)}일 전`;
}

function formatDiff(value: number) {
  if (value > 0) {
    return `+${value.toLocaleString()}`;
  }
  return value.toLocaleString();
}
