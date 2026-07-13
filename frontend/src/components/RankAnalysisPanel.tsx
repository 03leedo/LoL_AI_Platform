"use client";

import { BarChart3, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { LoadingState } from "@/components/StatusViews";
import { ConfidencePill } from "@/components/review/ConfidencePill";
import {
  getIngestJob,
  getRankAnalysis,
  IngestJob,
  IngestJobState,
  RankAnalysisResponse,
  RankRole,
  startSummonerIngest
} from "@/lib/api";
import { formatRole } from "@/lib/format";
import { LoadState } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

const ABILITY_ROWS: Array<{ key: string; label: string }> = [
  { key: "laning", label: "라인전" },
  { key: "combat", label: "교전" },
  { key: "objectives", label: "오브젝트" },
  { key: "map_awareness", label: "맵리딩·위험 인식" },
  { key: "lead_conversion", label: "리드 전환" },
  { key: "stability", label: "안정성" }
];

const ROLE_ORDER: RankRole[] = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];

const JOB_STATE_LABELS: Record<IngestJobState, string> = {
  queued: "대기 중",
  running: "수집 중",
  done: "완료",
  failed: "실패"
};

type IngestPhase = "idle" | "starting" | "polling" | "failed";

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, value));
}

function formatWinRate(value: number | null) {
  if (value === null) {
    return "-";
  }
  const percent = value <= 1 ? value * 100 : value;
  return `${Math.round(percent)}%`;
}

export function RankAnalysisPanel({ gameName, tagLine }: { gameName: string; tagLine: string }) {
  const [analysisState, setAnalysisState] = useState<LoadState>("loading");
  const [analysis, setAnalysis] = useState<RankAnalysisResponse | null>(null);
  const [analysisError, setAnalysisError] = useState("");
  const [ingestPhase, setIngestPhase] = useState<IngestPhase>("idle");
  const [job, setJob] = useState<IngestJob | null>(null);
  const [ingestError, setIngestError] = useState("");

  const mountedRef = useRef(true);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollBusyRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollBusyRef.current = false;
  }, []);

  const loadAnalysis = useCallback(async () => {
    setAnalysisState("loading");
    setAnalysisError("");

    try {
      const data = await getRankAnalysis(gameName, tagLine);
      if (!mountedRef.current) {
        return;
      }
      setAnalysis(data);
      setAnalysisState("success");
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      setAnalysisError(err instanceof Error ? err.message : "랭크 분석을 불러오지 못했습니다.");
      setAnalysisState("error");
    }
  }, [gameName, tagLine]);

  useEffect(() => {
    mountedRef.current = true;
    setIngestPhase("idle");
    setJob(null);
    setIngestError("");
    loadAnalysis();

    return () => {
      mountedRef.current = false;
      stopPolling();
    };
  }, [loadAnalysis, stopPolling]);

  const beginPolling = useCallback(
    (jobId: number) => {
      stopPolling();
      pollTimerRef.current = setInterval(async () => {
        if (pollBusyRef.current) {
          return;
        }
        pollBusyRef.current = true;

        try {
          const next = await getIngestJob(jobId);
          if (!mountedRef.current) {
            return;
          }
          setJob(next);

          if (next.state === "done") {
            stopPolling();
            setIngestPhase("idle");
            setJob(null);
            loadAnalysis();
          } else if (next.state === "failed") {
            stopPolling();
            setIngestPhase("failed");
            setIngestError(next.error ?? "경기 수집에 실패했습니다.");
          }
        } catch (err) {
          if (!mountedRef.current) {
            return;
          }
          stopPolling();
          setIngestPhase("failed");
          setIngestError(err instanceof Error ? err.message : "수집 상태 확인에 실패했습니다.");
        } finally {
          pollBusyRef.current = false;
        }
      }, POLL_INTERVAL_MS);
    },
    [loadAnalysis, stopPolling]
  );

  const startIngest = useCallback(async () => {
    setIngestPhase("starting");
    setIngestError("");
    setJob(null);

    try {
      const created = await startSummonerIngest(gameName, tagLine);
      if (!mountedRef.current) {
        return;
      }
      setJob(created);

      if (created.state === "done") {
        setIngestPhase("idle");
        setJob(null);
        loadAnalysis();
        return;
      }
      if (created.state === "failed") {
        setIngestPhase("failed");
        setIngestError(created.error ?? "경기 수집에 실패했습니다.");
        return;
      }

      setIngestPhase("polling");
      beginPolling(created.id);
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      setIngestPhase("failed");
      setIngestError(err instanceof Error ? err.message : "경기 수집 요청에 실패했습니다.");
    }
  }, [beginPolling, gameName, tagLine, loadAnalysis]);

  const ingestActive = ingestPhase === "starting" || ingestPhase === "polling";
  const progress = clampPercent(Math.round(job?.progress ?? 0));

  return (
    <section className="history-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Rank insight</p>
          <h2>랭크 분석</h2>
        </div>
        <BarChart3 size={22} aria-hidden="true" />
      </div>

      {analysisState === "loading" && <LoadingState label="랭크 분석 데이터를 불러오는 중입니다." />}

      {analysisState === "error" && (
        <div className="heatmap-idle">
          <p className="error-copy">{analysisError}</p>
          <button onClick={loadAnalysis} type="button">
            다시 시도
          </button>
        </div>
      )}

      {analysisState === "success" && analysis && (
        <div className="rank-analysis-body">
          {ingestActive && (
            <div className="ingest-progress">
              <div className="ingest-progress-header">
                <span className="ingest-state-label">
                  {job ? JOB_STATE_LABELS[job.state] : "대기 중"}
                </span>
                <span className="ingest-progress-value">{progress}%</span>
              </div>
              <div
                aria-valuemax={100}
                aria-valuemin={0}
                aria-valuenow={progress}
                className="progress-track"
                role="progressbar"
              >
                <span className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <p className="rank-ingest-note">수집은 1~2분 정도 걸려요.</p>
            </div>
          )}

          {ingestPhase === "failed" && (
            <div className="ingest-progress">
              <div className="ingest-progress-header">
                <span className="ingest-state-label is-failed">실패</span>
              </div>
              <p className="error-copy">{ingestError}</p>
              <button onClick={startIngest} type="button">
                다시 시도
              </button>
            </div>
          )}

          {analysis.needs_ingest && !ingestActive && ingestPhase !== "failed" && (
            <div className="heatmap-idle">
              <p>
                분석할 경기 데이터가 부족해요. 최근 랭크 경기를 수집하면 능력치 평가와 포지션 분석을
                볼 수 있어요.
              </p>
              <button onClick={startIngest} type="button">
                최근 20경기 수집하기
              </button>
              <p className="rank-ingest-note">수집은 1~2분 정도 걸려요.</p>
            </div>
          )}

          {!analysis.needs_ingest && (
            <>
              <div className="ability-section">
                <h3>공통 능력치</h3>
                <div className="ability-list">
                  {ABILITY_ROWS.map(({ key, label }) => {
                    const score = analysis.scorecard.abilities[key];
                    const value = score?.value ?? null;

                    return (
                      <div className="ability-row" key={key}>
                        <span className="ability-label">{label}</span>
                        <span aria-hidden="true" className="ability-bar">
                          <span
                            className="ability-bar-fill"
                            style={{ width: `${clampPercent(value ?? 0)}%` }}
                          />
                        </span>
                        <strong className={value === null ? "ability-value is-na" : "ability-value"}>
                          {value === null ? "N/A (표본 부족)" : Math.round(value)}
                        </strong>
                        <ConfidencePill confidence={score?.confidence ?? "low"} />
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="role-section">
                <h3>포지션 적합도</h3>
                <div className="role-grid">
                  {ROLE_ORDER.map((roleKey) => {
                    const role = analysis.roles.find((entry) => entry.role === roleKey);
                    const isRecommended = analysis.recommended.includes(roleKey);
                    const isCaution = analysis.caution === roleKey;
                    const hasSample = role !== undefined && role.games > 0;

                    const cardClass = [
                      "role-card",
                      hasSample ? "" : "is-dimmed",
                      isRecommended ? "is-recommended" : ""
                    ]
                      .filter(Boolean)
                      .join(" ");

                    return (
                      <div className={cardClass} key={roleKey}>
                        <div className="role-card-head">
                          <strong>{formatRole(roleKey)}</strong>
                          {isRecommended && <span className="role-badge">추천</span>}
                          {isCaution && <span className="role-badge caution">주의</span>}
                        </div>

                        {role !== undefined && role.games > 0 ? (
                          <>
                            <p className="role-fit">
                              <strong>
                                {role.fit_score === null ? "-" : Math.round(role.fit_score)}
                              </strong>
                              <span>적합도</span>
                            </p>
                            <p className="role-meta">
                              {role.games}경기 · 승률 {formatWinRate(role.win_rate)}
                            </p>
                            <ConfidencePill confidence={role.confidence} />
                          </>
                        ) : (
                          <p className="role-empty">표본 없음</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="rank-analysis-footer">
                <p className="rank-footnote">
                  최근 {analysis.games_analyzed}경기 기준 · 표본이 적은 포지션은 점수가 중앙(50)으로
                  보정됩니다
                </p>
                <button
                  className="rank-refresh-button"
                  disabled={ingestActive}
                  onClick={startIngest}
                  type="button"
                >
                  <RefreshCw size={14} aria-hidden="true" />
                  다시 수집하기
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
