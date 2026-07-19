"use client";

import { ChevronRight, Loader2 } from "lucide-react";

import { MatchSummary } from "@/lib/api";
import { championSplashUrl } from "@/lib/assets";
import {
  formatCompactNumber,
  formatCsPerMinute,
  formatDuration,
  formatGameTime,
  formatKda,
  formatPercent,
  formatRole,
  queueLabel
} from "@/lib/format";

export function MatchCard({
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

  const resultClass = match.win === null ? "" : match.win ? " is-win" : " is-loss";

  return (
    <article className={`match-card${resultClass}${isSelected ? " is-selected" : ""}`}>
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
            {match.win === null ? "결과 없음" : match.win ? "승리" : "패배"}
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

        <div className="match-stat-lines">
          <div className="match-card-stats is-primary">
            <span><strong>DMG</strong>{formatCompactNumber(match.total_damage_dealt_to_champions)}</span>
            <span><strong>KP</strong>{formatPercent(match.kill_participation)}</span>
            <span><strong>Gold</strong>{formatCompactNumber(match.gold_earned)}</span>
            <span><strong>Taken</strong>{formatCompactNumber(match.total_damage_taken)}</span>
          </div>
          <div className="match-card-stats">
            <span>CS {cs}</span>
            <span>CS/min {formatCsPerMinute(cs, match.game_duration)}</span>
            <span>Vision {match.vision_score ?? "-"}</span>
          </div>
        </div>
      </div>

      <button type="button" onClick={onReview} disabled={isLoading}>
        {isLoading ? <Loader2 className="spin" size={18} aria-hidden="true" /> : <ChevronRight size={18} aria-hidden="true" />}
        <span>자세히 보기</span>
      </button>
    </article>
  );
}
