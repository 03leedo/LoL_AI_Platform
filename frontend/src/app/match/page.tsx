"use client";

import { ArrowLeft, HelpCircle, ListChecks, Search } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LoadingState } from "@/components/StatusViews";
import { EvidencePanel } from "@/components/review/EvidencePanel";
import { MiniMetric } from "@/components/review/MiniMetric";
import { ScoreCard } from "@/components/review/ScoreCard";
import { TimelineChart } from "@/components/review/TimelineChart";
import { TurningPoints } from "@/components/review/TurningPoints";
import { WinCurveChart } from "@/components/review/WinCurveChart";
import {
  getMatchReview,
  MatchPlayerAnalysisResponse,
  MatchReviewAssets,
  MatchTimelineAnalysisResponse,
  MatchTurningPoint,
  PlayerAnalysisScore,
  ScoreGroup
} from "@/lib/api";
import { formatDiff, formatRole } from "@/lib/format";
import { LoadState } from "@/lib/types";

type ScoreCardEntry = {
  key: string;
  label: string;
  sublabel?: string;
  score: PlayerAnalysisScore;
};

const SCORE_GROUP_FALLBACK: Record<string, ScoreGroup> = {
  objective_setup_score: "performance",
  lead_conversion_score: "performance",
  stability_score: "performance",
  teamfight_persistence_score: "performance",
  death_cost_index: "risk_style",
  throw_index: "risk_style",
  gold_retention_score: "risk_style",
  gambler_index: "risk_style",
  death_acceleration_index: "risk_style"
};

function resolveScoreGroup(entry: ScoreCardEntry): ScoreGroup {
  return entry.score.group ?? SCORE_GROUP_FALLBACK[entry.key] ?? "performance";
}

function buildScoreCards(scores: MatchPlayerAnalysisResponse["scores"]): ScoreCardEntry[] {
  const cards: ScoreCardEntry[] = [
    { key: "death_cost_index", label: "Death Cost", score: scores.death_cost_index },
    { key: "throw_index", label: "Throw Index", score: scores.throw_index },
    { key: "stability_score", label: "Stability", score: scores.stability_score },
    { key: "objective_setup_score", label: "Objective", score: scores.objective_setup_score },
    { key: "lead_conversion_score", label: "Lead Conversion", score: scores.lead_conversion_score }
  ];

  if (scores.gold_retention_score) {
    cards.push({
      key: "gold_retention_score",
      label: "골드 리텐션",
      score: scores.gold_retention_score,
      sublabel: "킬 골드를 아이템으로 늦게 전환할수록 높음"
    });
  }
  if (scores.gambler_index) {
    cards.push({
      key: "gambler_index",
      label: "도박사 지수",
      score: scores.gambler_index,
      sublabel: "제압골 헌납·고립 데스·적진 침투 성향"
    });
  }
  if (scores.teamfight_persistence_score) {
    cards.push({
      key: "teamfight_persistence_score",
      label: "한타 지속력",
      score: scores.teamfight_persistence_score,
      sublabel: "한타에서 살아남으며 딜을 이어가는 능력"
    });
  }
  if (scores.death_acceleration_index) {
    cards.push({
      key: "death_acceleration_index",
      label: "데스 가속도",
      score: scores.death_acceleration_index,
      sublabel: "첫 데스 후 5분 내 연쇄 데스"
    });
  }

  return cards;
}

export default function MatchReviewPage() {
  return (
    <Suspense
      fallback={
        <main className="app-shell">
          <LoadingState label="경기 정보를 불러오는 중입니다." />
        </main>
      }
    >
      <MatchReviewPageInner />
    </Suspense>
  );
}

function MatchReviewPageInner() {
  const searchParams = useSearchParams();
  const matchId = searchParams.get("matchId") ?? "";
  const puuid = searchParams.get("puuid") ?? "";
  const gameName = searchParams.get("gameName") ?? "";
  const tagLine = searchParams.get("tagLine") ?? "";
  const backHref = gameName && tagLine
    ? `/summoner?${new URLSearchParams({ gameName, tagLine }).toString()}`
    : "/";

  const [reviewState, setReviewState] = useState<LoadState>("loading");
  const [timeline, setTimeline] = useState<MatchTimelineAnalysisResponse | null>(null);
  const [playerAnalysis, setPlayerAnalysis] = useState<MatchPlayerAnalysisResponse | null>(null);
  const [reviewAssets, setReviewAssets] = useState<MatchReviewAssets | null>(null);
  const [turningPoints, setTurningPoints] = useState<MatchTurningPoint[]>([]);
  const [reviewError, setReviewError] = useState("");

  useEffect(() => {
    setReviewState("loading");
    setReviewError("");
    setTimeline(null);
    setPlayerAnalysis(null);
    setReviewAssets(null);
    setTurningPoints([]);

    if (!matchId || !puuid) {
      setReviewError("경기 분석에 필요한 정보가 부족합니다. 전적 목록에서 다시 열어주세요.");
      setReviewState("error");
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const review = await getMatchReview({ matchId, puuid, gameName, tagLine });
        if (cancelled) {
          return;
        }
        setTimeline(review.timeline);
        setPlayerAnalysis(review.analysis);
        setReviewAssets(review.assets);
        setTurningPoints(review.turning_points ?? []);
        setReviewState("success");
      } catch (err) {
        if (cancelled) {
          return;
        }
        setReviewError(err instanceof Error ? err.message : "경기 분석에 실패했습니다.");
        setReviewState("error");
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [matchId, puuid]);

  const latestFrame = timeline?.frames[timeline.frames.length - 1];
  const winCurve = timeline?.win_curve ?? [];

  const scoreCards = playerAnalysis ? buildScoreCards(playerAnalysis.scores) : [];
  const performanceCards = scoreCards.filter((entry) => resolveScoreGroup(entry) === "performance");
  const riskStyleCards = scoreCards.filter((entry) => resolveScoreGroup(entry) === "risk_style");
  const statements = playerAnalysis?.statements ?? [];
  const replayQuestions = statements.filter((statement) => statement.kind === "replay_question");
  const hasLimitation = statements.some((statement) => statement.kind === "limitation");

  return (
    <main className="app-shell">
      <div className="page-toolbar">
        <Link className="back-link" href={backHref}>
          {gameName && tagLine ? (
            <>
              <ArrowLeft size={16} aria-hidden="true" />
              <span>전적 목록으로</span>
            </>
          ) : (
            <>
              <Search size={16} aria-hidden="true" />
              <span>소환사 검색으로</span>
            </>
          )}
        </Link>
      </div>

      <section className="match-layout is-single">
        <aside className="review-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Review</p>
              <h2>경기 분석</h2>
            </div>
            <ListChecks size={22} aria-hidden="true" />
          </div>

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

              {performanceCards.length > 0 && (
                <div className="score-group">
                  <div className="score-group-head">
                    <h3>퍼포먼스 지표</h3>
                    <span className="score-group-note">높을수록 좋음</span>
                  </div>
                  <div className="score-grid">
                    {performanceCards.map((entry) => (
                      <ScoreCard
                        key={entry.key}
                        label={entry.label}
                        score={entry.score}
                        sublabel={entry.sublabel}
                      />
                    ))}
                  </div>
                </div>
              )}

              {riskStyleCards.length > 0 && (
                <div className="score-group">
                  <div className="score-group-head">
                    <h3>위험·스타일 신호</h3>
                    <span className="score-group-note">높을수록 강한 경향 · 능력 점수가 아닙니다</span>
                  </div>
                  <div className="score-grid">
                    {riskStyleCards.map((entry) => (
                      <ScoreCard
                        key={entry.key}
                        label={entry.label}
                        score={entry.score}
                        sublabel={entry.sublabel}
                      />
                    ))}
                  </div>
                </div>
              )}

              {hasLimitation && (
                <p className="score-limitation-note">
                  일부 판정은 1분 단위 데이터 근사입니다 · 자세한 한계는 AI 리포트에서 확인
                </p>
              )}

              {latestFrame && (
                <div className="timeline-summary">
                  <MiniMetric
                    label="Gold"
                    value={formatDiff(
                      latestFrame.gold_diff * (playerAnalysis.player.team === "red" ? -1 : 1)
                    )}
                  />
                  <MiniMetric
                    label="XP"
                    value={formatDiff(
                      latestFrame.xp_diff * (playerAnalysis.player.team === "red" ? -1 : 1)
                    )}
                  />
                  <MiniMetric
                    label="CS"
                    value={formatDiff(
                      latestFrame.cs_diff * (playerAnalysis.player.team === "red" ? -1 : 1)
                    )}
                  />
                </div>
              )}

              <div className="win-curve-section">
                <h3>골드 우세도 흐름</h3>
                <TimelineChart frames={timeline.frames} team={playerAnalysis.player.team} />
              </div>

              {winCurve.length >= 2 && (
                <div className="win-curve-section">
                  <h3>
                    {timeline.win_curve_source === "model_v1_experimental"
                      ? "모델 예상 승률 흐름"
                      : "예상 승률 흐름"}
                  </h3>
                  <WinCurveChart
                    points={winCurve}
                    team={playerAnalysis.player.team}
                    source={timeline.win_curve_source}
                    modelVersion={timeline.win_curve_model_version}
                  />
                </div>
              )}

              {turningPoints.length > 0 && <TurningPoints points={turningPoints} />}

              <EvidencePanel assets={reviewAssets} evidence={playerAnalysis.evidence} />

              {replayQuestions.length > 0 && (
                <div className="replay-question-section">
                  <h3>복기 질문</h3>
                  <ul className="replay-question-list">
                    {replayQuestions.map((statement, index) => (
                      <li key={`replay-question-${index}`}>
                        <HelpCircle size={14} aria-hidden="true" />
                        <span>{statement.text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}
