"use client";

import { ArrowLeft, ListChecks, Search } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LoadingState } from "@/components/StatusViews";
import { EvidencePanel } from "@/components/review/EvidencePanel";
import { MiniMetric } from "@/components/review/MiniMetric";
import { ScoreCard } from "@/components/review/ScoreCard";
import { TimelineChart } from "@/components/review/TimelineChart";
import { WinCurveChart } from "@/components/review/WinCurveChart";
import {
  getMatchReview,
  MatchPlayerAnalysisResponse,
  MatchReviewAssets,
  MatchTimelineAnalysisResponse
} from "@/lib/api";
import { formatDiff, formatRole } from "@/lib/format";
import { LoadState } from "@/lib/types";

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
  const params = useParams<{ matchId: string }>();
  const searchParams = useSearchParams();

  const matchIdParam = params?.matchId;
  const matchId = typeof matchIdParam === "string" ? safeDecode(matchIdParam) : "";
  const puuid = searchParams.get("puuid") ?? "";
  const riotId = searchParams.get("riotId") ?? "";

  const [reviewState, setReviewState] = useState<LoadState>("loading");
  const [timeline, setTimeline] = useState<MatchTimelineAnalysisResponse | null>(null);
  const [playerAnalysis, setPlayerAnalysis] = useState<MatchPlayerAnalysisResponse | null>(null);
  const [reviewAssets, setReviewAssets] = useState<MatchReviewAssets | null>(null);
  const [reviewError, setReviewError] = useState("");

  useEffect(() => {
    setReviewState("loading");
    setReviewError("");
    setTimeline(null);
    setPlayerAnalysis(null);
    setReviewAssets(null);

    if (!matchId || !puuid) {
      setReviewError("경기 분석에 필요한 정보가 부족합니다. 전적 목록에서 다시 열어주세요.");
      setReviewState("error");
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const review = await getMatchReview({ matchId, puuid });
        if (cancelled) {
          return;
        }
        setTimeline(review.timeline);
        setPlayerAnalysis(review.analysis);
        setReviewAssets(review.assets);
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

  return (
    <main className="app-shell">
      <div className="page-toolbar">
        {riotId ? (
          <Link className="back-link" href={`/summoner/${riotId}`}>
            <ArrowLeft size={16} aria-hidden="true" />
            <span>전적 목록으로</span>
          </Link>
        ) : (
          <Link className="back-link" href="/">
            <Search size={16} aria-hidden="true" />
            <span>소환사 검색으로</span>
          </Link>
        )}
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

              <div className="score-grid">
                <ScoreCard label="Death Cost" score={playerAnalysis.scores.death_cost_index} />
                <ScoreCard label="Throw Index" score={playerAnalysis.scores.throw_index} />
                <ScoreCard label="Stability" score={playerAnalysis.scores.stability_score} />
                <ScoreCard label="Objective" score={playerAnalysis.scores.objective_setup_score} />
                <ScoreCard label="Lead Conversion" score={playerAnalysis.scores.lead_conversion_score} />
                {playerAnalysis.scores.gold_retention_score && (
                  <ScoreCard
                    label="골드 리텐션"
                    score={playerAnalysis.scores.gold_retention_score}
                    sublabel="킬 골드를 아이템으로 늦게 전환할수록 높음"
                  />
                )}
                {playerAnalysis.scores.gambler_index && (
                  <ScoreCard
                    label="도박사 지수"
                    score={playerAnalysis.scores.gambler_index}
                    sublabel="제압골 헌납·고립 데스·적진 침투 성향"
                  />
                )}
                {playerAnalysis.scores.teamfight_persistence_score && (
                  <ScoreCard
                    label="한타 지속력"
                    score={playerAnalysis.scores.teamfight_persistence_score}
                    sublabel="한타에서 살아남으며 딜을 이어가는 능력"
                  />
                )}
                {playerAnalysis.scores.death_acceleration_index && (
                  <ScoreCard
                    label="데스 가속도"
                    score={playerAnalysis.scores.death_acceleration_index}
                    sublabel="첫 데스 후 5분 내 연쇄 데스"
                  />
                )}
              </div>

              {latestFrame && (
                <div className="timeline-summary">
                  <MiniMetric label="Gold" value={formatDiff(latestFrame.gold_diff)} />
                  <MiniMetric label="XP" value={formatDiff(latestFrame.xp_diff)} />
                  <MiniMetric label="CS" value={formatDiff(latestFrame.cs_diff)} />
                </div>
              )}

              <TimelineChart frames={timeline.frames} />

              {winCurve.length >= 2 && (
                <div className="win-curve-section">
                  <h3>승률 흐름</h3>
                  <WinCurveChart points={winCurve} team={playerAnalysis.player.team} />
                </div>
              )}

              <EvidencePanel assets={reviewAssets} evidence={playerAnalysis.evidence} />
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}

function safeDecode(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}
