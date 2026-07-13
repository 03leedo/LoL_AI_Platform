"use client";

import { Search, Swords } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MatchCard } from "@/components/MatchCard";
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

function parseRiotId(riotId: string): { gameName: string; tagLine: string } | null {
  const separatorIndex = riotId.lastIndexOf("-");
  if (separatorIndex <= 0 || separatorIndex === riotId.length - 1) {
    return null;
  }

  try {
    return {
      gameName: decodeURIComponent(riotId.slice(0, separatorIndex)),
      tagLine: decodeURIComponent(riotId.slice(separatorIndex + 1))
    };
  } catch {
    return null;
  }
}

export default function SummonerPage() {
  const router = useRouter();
  const params = useParams<{ riotId: string }>();
  const riotIdParam = params?.riotId;
  const riotId = typeof riotIdParam === "string" ? riotIdParam : "";
  const parsedRiotId = parseRiotId(riotId);

  const [lookupState, setLookupState] = useState<LoadState>("loading");
  const [lookup, setLookup] = useState<SummonerLookupResponse | null>(null);
  const [lookupError, setLookupError] = useState("");
  const [matchState, setMatchState] = useState<LoadState>("idle");
  const [matchHistory, setMatchHistory] = useState<MatchSummary[]>([]);
  const [matchError, setMatchError] = useState("");
  const [pendingMatchId, setPendingMatchId] = useState("");

  useEffect(() => {
    const parsed = parseRiotId(riotId);

    setLookupState("loading");
    setLookupError("");
    setLookup(null);
    setMatchState("idle");
    setMatchHistory([]);
    setMatchError("");
    setPendingMatchId("");

    if (!parsed) {
      setLookupError("소환사 주소가 올바르지 않습니다. 다시 검색해주세요.");
      setLookupState("error");
      return;
    }

    let cancelled = false;

    async function load(gameName: string, tagLine: string) {
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

    load(parsed.gameName, parsed.tagLine);

    return () => {
      cancelled = true;
    };
  }, [riotId]);

  function onReviewMatch(matchId: string) {
    if (!lookup) {
      return;
    }

    setPendingMatchId(matchId);
    router.push(
      `/match/${encodeURIComponent(matchId)}?puuid=${encodeURIComponent(lookup.account.puuid)}&riotId=${encodeURIComponent(riotId)}`
    );
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

        {lookupState === "success" && parsedRiotId && (
          <>
            <SummonerHeatmap
              key={riotId}
              gameName={parsedRiotId.gameName}
              tagLine={parsedRiotId.tagLine}
            />
            <RankAnalysisPanel
              key={`rank-${riotId}`}
              gameName={parsedRiotId.gameName}
              tagLine={parsedRiotId.tagLine}
            />
            <PlayerReportPanel
              key={`report-${riotId}`}
              gameName={parsedRiotId.gameName}
              tagLine={parsedRiotId.tagLine}
            />
          </>
        )}
      </section>
    </main>
  );
}

function formatSoloRank(summoner: SummonerLookupResponse["summoner"]): string | null {
  if (!summoner.solo_tier) {
    return null;
  }

  const parts: string[] = [
    [summoner.solo_tier, summoner.solo_division].filter(Boolean).join(" ")
  ];

  if (summoner.solo_lp !== null) {
    parts.push(`${summoner.solo_lp} LP`);
  }

  const wins = summoner.solo_wins ?? 0;
  const losses = summoner.solo_losses ?? 0;
  const total = wins + losses;
  if (total > 0) {
    parts.push(`승률 ${Math.round((wins / total) * 100)}% (${wins}승 ${losses}패)`);
  }

  return parts.join(" · ");
}
