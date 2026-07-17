"use client";

import { Layers } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { LoadingState } from "@/components/StatusViews";
import {
  getRepresentativeMatches,
  MatchSelection,
  MatchSelectionKind,
  MatchSelectionsResponse
} from "@/lib/api";
import { formatRole } from "@/lib/format";
import { LoadState } from "@/lib/types";

const SELECTION_WINDOW = 20;

const SELECTION_CARDS: Array<{
  kind: MatchSelectionKind;
  title: string;
  subtitle: string;
}> = [
  {
    kind: "representative",
    title: "대표 경기",
    subtitle: "평소의 나와 가장 가까운 경기"
  },
  {
    kind: "best",
    title: "최고 퍼포먼스",
    subtitle: "상황 보정 지표 종합 최고"
  },
  {
    kind: "deviation",
    title: "평소와 달랐던 경기",
    subtitle: "가장 달랐던 경기 — 못한 경기라는 뜻이 아닙니다"
  }
];

function formatScore(value: number) {
  return Math.abs(value) >= 10 ? Math.round(value).toString() : value.toFixed(1);
}

function formatDiff(value: number) {
  return `${value >= 0 ? "+" : ""}${formatScore(value)}`;
}

export function RepresentativeMatchesPanel({
  gameName,
  tagLine,
  puuid,
  riotId
}: {
  gameName: string;
  tagLine: string;
  puuid: string;
  riotId: string;
}) {
  const [selectionState, setSelectionState] = useState<LoadState>("loading");
  const [selections, setSelections] = useState<MatchSelectionsResponse | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadSelections = useCallback(async () => {
    setSelectionState("loading");
    setSelectionError("");

    try {
      const data = await getRepresentativeMatches(gameName, tagLine, SELECTION_WINDOW);
      if (!mountedRef.current) {
        return;
      }
      setSelections(data);
      setSelectionState("success");
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      setSelectionError(err instanceof Error ? err.message : "대표 경기 선정을 불러오지 못했습니다.");
      setSelectionState("error");
    }
  }, [gameName, tagLine]);

  useEffect(() => {
    setSelections(null);
    loadSelections();
  }, [loadSelections]);

  return (
    <section className="history-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Match selections</p>
          <h2>대표 · 최고 · 이탈 경기</h2>
        </div>
        <Layers size={22} aria-hidden="true" />
      </div>

      <div className="selection-panel-body">
        {selectionState === "loading" && <LoadingState label="대표 경기 선정을 불러오는 중입니다." />}

        {selectionState === "error" && (
          <div className="heatmap-idle">
            <p className="error-copy">{selectionError}</p>
            <button onClick={loadSelections} type="button">
              다시 시도
            </button>
          </div>
        )}

        {selectionState === "success" && selections && selections.insufficient_data && (
          <div className="heatmap-idle">
            <p>
              선정할 만한 경기 표본이 부족해요 (포지션 경기 5판 이상 필요). 랭크 분석에서 수집을
              실행해 주세요.
            </p>
          </div>
        )}

        {selectionState === "success" && selections && !selections.insufficient_data && (
          <>
            <div>
              <p className="profile-meta">
                {formatRole(selections.role)} · 최근 {selections.games_considered}경기 중{" "}
                {selections.eligible_matches}경기 비교 (제외 {selections.excluded_matches})
              </p>
              <p className="profile-meta-sub">기본: 주 포지션</p>
            </div>

            <div className="selection-grid">
              {SELECTION_CARDS.map(({ kind, title, subtitle }) => (
                <SelectionCard
                  key={kind}
                  kind={kind}
                  title={title}
                  subtitle={subtitle}
                  selection={selections[kind]}
                  puuid={puuid}
                  riotId={riotId}
                />
              ))}
            </div>

            <p className="rank-footnote">
              선정은 결정적 규칙(v{selections.selection_version})이며 프로필과 같은 수식을
              사용합니다.
            </p>
          </>
        )}
      </div>
    </section>
  );
}

function SelectionCard({
  kind,
  title,
  subtitle,
  selection,
  puuid,
  riotId
}: {
  kind: MatchSelectionKind;
  title: string;
  subtitle: string;
  selection: MatchSelection | null;
  puuid: string;
  riotId: string;
}) {
  return (
    <div className="selection-card">
      <div className="selection-card-head">
        <span className={`selection-kind-badge is-${kind}`}>{title}</span>
      </div>
      <p className="selection-subtitle">{subtitle}</p>

      {selection === null ? (
        <p className="selection-empty">선정 불가</p>
      ) : (
        <>
          <div className="selection-mainline">
            <strong className="selection-champion">{selection.champion_name ?? "Unknown"}</strong>
            <span
              className={
                selection.win === null
                  ? "result-badge"
                  : selection.win
                    ? "result-badge win"
                    : "result-badge loss"
              }
            >
              {selection.win === null ? "-" : selection.win ? "승" : "패"}
            </span>
          </div>

          <p className="selection-reason">{selection.reason}</p>

          {selection.drivers.length > 0 && (
            <div className="selection-driver-list">
              {selection.drivers.map((driver) => (
                <p className="selection-driver-row" key={driver.key}>
                  {driver.label}: {formatScore(driver.value)}점 (평소{" "}
                  {formatScore(driver.profile_value)}점, {formatDiff(driver.diff)})
                </p>
              ))}
            </div>
          )}

          <Link
            className="selection-review-link"
            href={`/match/${selection.match_id}?puuid=${puuid}&riotId=${encodeURIComponent(riotId)}`}
          >
            이 경기 복기 →
          </Link>
        </>
      )}
    </div>
  );
}
