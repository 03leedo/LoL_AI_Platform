"use client";

import { Search, Swords } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { MatchCard } from "@/components/MatchCard";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { PlayerReportPanel } from "@/components/PlayerReportPanel";
import { RankAnalysisPanel } from "@/components/RankAnalysisPanel";
import { EmptyState, LoadingState } from "@/components/StatusViews";
import { SummonerHeatmap } from "@/components/SummonerHeatmap";
import {
  getSummonerMatchHistory,
  MatchSummary,
  searchSummoner,
  SummonerLookupResponse
} from "@/lib/api";
import { LoadState } from "@/lib/types";

const RECENT_MATCH_COUNT = 8;

export default function SummonerPage() {
  return (
    <Suspense
      fallback={
        <main className="app-shell">
          <LoadingState label="소환사 정보를 불러오는 중입니다." />
        </main>
      }
    >
      <SummonerPageInner />
    </Suspense>
  );
}

function SummonerPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const gameName = searchParams.get("gameName")?.trim() ?? "";
  const tagLine = searchParams.get("tagLine")?.trim() ?? "";
  const hasRiotId = Boolean(gameName && tagLine);

  const [lookupState, setLookupState] = useState<LoadState>("loading");
  const [lookup, setLookup] = useState<SummonerLookupResponse | null>(null);
  const [lookupError, setLookupError] = useState("");
  const [matchState, setMatchState] = useState<LoadState>("idle");
  const [matchHistory, setMatchHistory] = useState<MatchSummary[]>([]);
  const [matchError, setMatchError] = useState("");
  const [pendingMatchId, setPendingMatchId] = useState("");

  useEffect(() => {
    setLookupState("loading");
    setLookupError("");
    setLookup(null);
    setMatchState("idle");
    setMatchHistory([]);
    setMatchError("");
    setPendingMatchId("");

    if (!hasRiotId) {
      setLookupError("소환사 주소가 올바르지 않습니다. 다시 검색해주세요.");
      setLookupState("error");
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const data = await searchSummoner({ gameName, tagLine });
        if (cancelled) {
          return;
        }
        setLookup(data);
        setLookupState("success");
      } catch (err) {
        if (cancelled) {
          return;
        }
        setLookupError(err instanceof Error ? err.message : "소환사 검색에 실패했습니다.");
        setLookupState("error");
        return;
      }

      setMatchState("loading");
      try {
        const history = await getSummonerMatchHistory({
          gameName,
          tagLine,
          count: RECENT_MATCH_COUNT
        });
        if (cancelled) {
          return;
        }
        setMatchHistory(history.matches);
        setMatchState("success");
      } catch (err) {
        if (cancelled) {
          return;
        }
        setMatchError(err instanceof Error ? err.message : "최근 전적을 불러오지 못했습니다.");
        setMatchState("error");
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [gameName, tagLine, hasRiotId]);

  function onReviewMatch(matchId: string) {
    if (!lookup) {
      return;
    }

    setPendingMatchId(matchId);
    const params = new URLSearchParams({
      matchId,
      puuid: lookup.account.puuid,
      gameName,
      tagLine
    });
    router.push(`/match?${params.toString()}`);
  }

  return (
    <main className="app-shell">
      <div className="page-toolbar">
        <Link className="back-link" href="/">
          <Search size={16} aria-hidden="true" />
          <span>다른 소환사 검색</span>
        </Link>
      </div>

      {lookupState === "loading" && <LoadingState label="소환사 정보를 불러오는 중입니다." />}
      {lookupState === "error" && <p className="error-copy">{lookupError}</p>}

      {lookupState === "success" && lookup && (
        <section className="summoner-strip">
          <div>
            <span className="summoner-avatar">{lookup.account.game_name.slice(0, 1).toUpperCase()}</span>
          </div>
          <div className="summoner-info">
            <p>{lookup.account.game_name}#{lookup.account.tag_line}</p>
            <span>Level {lookup.summoner.summoner_level ?? "-"} · {lookup.summoner.platform_routing.toUpperCase()}</span>
            <div className="summoner-rank">
              {(() => {
                const rankLabel = formatSoloRank(lookup.summoner);
                return rankLabel ? (
                  <span className="rank-badge">{rankLabel}</span>
                ) : (
                  <span className="rank-badge is-unranked">언랭크</span>
                );
              })()}
            </div>
          </div>
        </section>
      )}

      <section className="match-layout is-single">
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
                  isSelected={pendingMatchId === match.match_id}
                  isLoading={pendingMatchId === match.match_id}
                  onReview={() => onReviewMatch(match.match_id)}
                />
              ))}
            </div>
          )}
        </section>

        {lookupState === "success" && hasRiotId && (
          <>
            <SummonerHeatmap
              key={`${gameName}-${tagLine}`}
              gameName={gameName}
              tagLine={tagLine}
            />
            <RankAnalysisPanel
              key={`rank-${gameName}-${tagLine}`}
              gameName={gameName}
              tagLine={tagLine}
            />
            <PlayerProfilePanel
              key={`profile-${gameName}-${tagLine}`}
              gameName={gameName}
              tagLine={tagLine}
            />
            <PlayerReportPanel
              key={`report-${gameName}-${tagLine}`}
              gameName={gameName}
              tagLine={tagLine}
            />
          </>
        )}
      </section>
    </main>
  );
}

function formatSoloRank(summoner: SummonerLookupResponse["summoner"]) {
  if (!summoner.solo_tier || !summoner.solo_division) {
    return null;
  }

  const lp = summoner.solo_lp ?? 0;
  const wins = summoner.solo_wins ?? 0;
  const losses = summoner.solo_losses ?? 0;
  return `${summoner.solo_tier} ${summoner.solo_division} · ${lp}LP · ${wins}W ${losses}L`;
}
