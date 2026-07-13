"use client";

import { RefreshCw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { LoadingState } from "@/components/StatusViews";
import { getPlayerReport, PlayerReportResponse, PlayerReportSeverity } from "@/lib/api";
import { LoadState } from "@/lib/types";

const REPORT_WINDOW = 20;

const SEVERITY_CLASSES: Record<PlayerReportSeverity, string> = {
  critical: "is-critical",
  warn: "is-warn",
  positive: "is-positive"
};

export function PlayerReportPanel({ gameName, tagLine }: { gameName: string; tagLine: string }) {
  const [reportState, setReportState] = useState<LoadState>("idle");
  const [report, setReport] = useState<PlayerReportResponse | null>(null);
  const [reportError, setReportError] = useState("");
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const generate = useCallback(
    async (force: boolean) => {
      setReportState("loading");
      setReportError("");

      try {
        const data = await getPlayerReport(gameName, tagLine, REPORT_WINDOW, force);
        if (!mountedRef.current) {
          return;
        }
        setReport(data);
        setReportState("success");
      } catch (err) {
        if (!mountedRef.current) {
          return;
        }
        setReportError(err instanceof Error ? err.message : "AI 리포트를 생성하지 못했습니다.");
        setReportState("error");
      }
    },
    [gameName, tagLine]
  );

  const autopsy = report?.autopsy ?? null;
  const hasStrengths = (report?.strengths.length ?? 0) > 0;
  const hasWeaknesses = (report?.weaknesses.length ?? 0) > 0;

  return (
    <section className="history-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">AI report</p>
          <h2>AI 종합 리포트</h2>
        </div>
        <Sparkles size={22} aria-hidden="true" />
      </div>

      {reportState === "idle" && (
        <div className="heatmap-idle">
          <p>수집된 최근 경기에서 반복되는 패턴을 찾아 근거와 함께 리포트를 만듭니다.</p>
          <button onClick={() => generate(false)} type="button">
            리포트 생성
          </button>
        </div>
      )}

      {reportState === "loading" && <LoadingState label="리포트 생성 중… (몇 초 걸릴 수 있어요)" />}

      {reportState === "error" && (
        <div className="heatmap-idle">
          <p className="error-copy">{reportError}</p>
          <button onClick={() => generate(false)} type="button">
            다시 시도
          </button>
        </div>
      )}

      {reportState === "success" && report && report.needs_ingest && (
        <div className="heatmap-idle">
          <p>리포트를 만들려면 먼저 랭크 분석에서 최근 경기를 수집해 주세요.</p>
        </div>
      )}

      {reportState === "success" && report && !report.needs_ingest && (
        <div className="player-report-body">
          <div className="report-meta">
            <div className="report-meta-pills">
              <span className={report.generated_by === "llm" ? "report-pill" : "report-pill is-rules"}>
                {report.generated_by === "llm" ? "AI 생성" : "규칙 기반"}
              </span>
              {report.cached && <span className="report-pill is-cached">캐시됨</span>}
              <span className="report-meta-text">최근 {report.games_analyzed}경기 기준</span>
            </div>
            <button className="rank-refresh-button" onClick={() => generate(true)} type="button">
              <RefreshCw size={14} aria-hidden="true" />
              다시 생성
            </button>
          </div>

          <div className="report-section">
            <h3>요약</h3>
            <p className="report-summary">{report.summary}</p>
          </div>

          {(hasStrengths || hasWeaknesses) && (
            <div className={hasStrengths && hasWeaknesses ? "report-columns" : "report-columns is-single"}>
              {hasStrengths && (
                <div className="report-list-block is-strength">
                  <h3>강점</h3>
                  <ul>
                    {report.strengths.map((item, index) => (
                      <li key={`strength-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {hasWeaknesses && (
                <div className="report-list-block is-weakness">
                  <h3>약점</h3>
                  <ul>
                    {report.weaknesses.map((item, index) => (
                      <li key={`weakness-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {report.recommendations.length > 0 && (
            <div className="report-section">
              <h3>개선 제안</h3>
              <ol className="report-recommendations">
                {report.recommendations.map((item, index) => (
                  <li key={`recommendation-${index}`}>{item}</li>
                ))}
              </ol>
            </div>
          )}

          {report.patterns.length > 0 && (
            <div className="report-section">
              <h3>반복 패턴</h3>
              <div className="pattern-list">
                {report.patterns.map((pattern) => (
                  <div className={`pattern-card ${SEVERITY_CLASSES[pattern.severity]}`} key={pattern.key}>
                    <div className="pattern-head">
                      <strong>{pattern.title}</strong>
                      {pattern.stat && <span className="pattern-stat">{pattern.stat}</span>}
                    </div>
                    <p>{pattern.description}</p>
                    <span className="pattern-footer">{pattern.matches.length}판에서 관측</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {autopsy && autopsy.deaths > 0 && (
            <div className="report-section">
              <h3>데스 부검 요약</h3>
              <div className="autopsy-chips">
                <span className="autopsy-chip">
                  데스 <strong>{autopsy.deaths}</strong> / 킬 <strong>{autopsy.kills}</strong>
                </span>
                <span className="autopsy-chip">
                  제압골 헌납 <strong>{autopsy.shutdown_deaths}회</strong> ·{" "}
                  <strong>{autopsy.shutdown_gold_conceded}G</strong>
                </span>
                <span className="autopsy-chip">
                  데스→오브젝트 손실 <strong>{Math.round(autopsy.objective_linked_share * 100)}%</strong>
                </span>
                {autopsy.avg_first_death_minute !== null && (
                  <span className="autopsy-chip">
                    평균 첫 데스 <strong>{autopsy.avg_first_death_minute}분</strong>
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
