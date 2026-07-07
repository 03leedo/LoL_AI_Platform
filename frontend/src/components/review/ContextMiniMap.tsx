"use client";

import { Eye } from "lucide-react";

import { EventGlyph } from "@/components/review/EventGlyph";
import { EvidenceContext, EvidenceContextSnapshot, MatchReviewAssets } from "@/lib/api";
import { championIconUrl, championInitial, mapCoord, mapImageUrl } from "@/lib/assets";
import { teamLabel } from "@/lib/format";

export function ContextMiniMap({
  assets,
  context,
  snapshot
}: {
  assets: MatchReviewAssets | null;
  context: EvidenceContext;
  snapshot: EvidenceContextSnapshot;
}) {
  const visibleEvents = context.events.filter(
    (event) => !event.type.startsWith("ward_") && Math.abs(event.timestamp_ms - snapshot.timestamp_ms) <= 45_000
  );

  return (
    <div
      aria-label={`${snapshot.minute}분 미니맵 스냅샷`}
      className="context-map"
      role="img"
      style={{ backgroundImage: `url(${mapImageUrl(assets?.map_id ?? 11)})` }}
    >
      <span className="map-overlay" />

      {snapshot.participants.map((participant) => (
        <span
          className={[
            "champion-marker",
            participant.team,
            participant.is_player ? "is-player" : ""
          ].join(" ")}
          key={participant.participant_id}
          style={{
            left: `${mapCoord(participant.x)}%`,
            top: `${100 - mapCoord(participant.y)}%`
          }}
          title={`${participant.champion_name ?? `P${participant.participant_id}`} · ${teamLabel(participant.team)}`}
        >
          <span>{championInitial(participant.champion_name, participant.participant_id)}</span>
          {assets?.data_dragon_version && participant.champion_name && (
            <img
              alt=""
              loading="lazy"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
              src={championIconUrl(participant.champion_name, assets.data_dragon_version)}
            />
          )}
        </span>
      ))}

      {snapshot.ward_events.map((event, index) => (
        event.position_x !== null && event.position_y !== null && (
          <span
            className={`ward-marker ${event.team} ${event.type}`}
            key={`${event.timestamp_ms}-${event.type}-${index}`}
            style={{
              left: `${mapCoord(event.position_x)}%`,
              top: `${100 - mapCoord(event.position_y)}%`
            }}
            title={`${event.title} · ${teamLabel(event.team)}`}
          >
            <Eye size={11} aria-hidden="true" />
          </span>
        )
      ))}

      {visibleEvents.map((event, index) => (
        event.position_x !== null && event.position_y !== null && (
          <span
            className={`event-pin ${event.type}`}
            key={`${event.timestamp_ms}-${event.type}-${index}`}
            style={{
              left: `${mapCoord(event.position_x)}%`,
              top: `${100 - mapCoord(event.position_y)}%`
            }}
            title={event.title}
          >
            <EventGlyph type={event.type} />
          </span>
        )
      ))}
    </div>
  );
}
