"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useState } from "react";

import { ConfidencePill } from "@/components/review/ConfidencePill";
import { ContextMiniMap } from "@/components/review/ContextMiniMap";
import { EventGlyph } from "@/components/review/EventGlyph";
import { MiniMetric } from "@/components/review/MiniMetric";
import {
  EvidenceContext,
  EvidenceContextEvent,
  EvidenceContextSnapshot,
  MatchReviewAssets,
  PlayerAnalysisEvidence
} from "@/lib/api";
import { eventTypeLabel, formatOffset, teamLabel } from "@/lib/format";

export function EvidencePanel({
  assets,
  evidence
}: {
  assets: MatchReviewAssets | null;
  evidence: PlayerAnalysisEvidence[];
}) {
  return (
    <div className="evidence-panel">
      <h3>주요 근거</h3>
      <div className="evidence-list">
        {evidence.map((item, index) => (
          <EvidenceItem
            assets={assets}
            evidence={item}
            key={`${item.type}-${item.minute}-${index}`}
          />
        ))}
      </div>
    </div>
  );
}

function EvidenceItem({
  assets,
  evidence
}: {
  assets: MatchReviewAssets | null;
  evidence: PlayerAnalysisEvidence;
}) {
  return (
    <article className="evidence-item">
      <div className="evidence-header">
        <div>
          <span className="evidence-minute">{evidence.minute}m</span>
          <strong>{evidence.title}</strong>
        </div>
        <ConfidencePill confidence={evidence.confidence} />
      </div>
      <p>{evidence.description}</p>
      {evidence.context && <EvidenceContextViewer assets={assets} context={evidence.context} />}
    </article>
  );
}

function EvidenceContextViewer({
  assets,
  context
}: {
  assets: MatchReviewAssets | null;
  context: EvidenceContext;
}) {
  const anchorIndex = Math.max(
    0,
    context.snapshots.findIndex((snapshot) => snapshot.timestamp_ms >= context.anchor_timestamp_ms)
  );
  const [frameIndex, setFrameIndex] = useState(anchorIndex);
  const [isPlaying, setIsPlaying] = useState(false);
  const frameCount = context.snapshots.length;
  const activeIndex = Math.min(frameIndex, Math.max(0, frameCount - 1));
  const activeSnapshot = context.snapshots[activeIndex];

  useEffect(() => {
    setFrameIndex(anchorIndex);
    setIsPlaying(false);
  }, [anchorIndex, context.anchor_timestamp_ms]);

  useEffect(() => {
    if (!isPlaying || frameCount < 2) {
      return;
    }

    const timer = window.setInterval(() => {
      setFrameIndex((current) => (current >= frameCount - 1 ? 0 : current + 1));
    }, 900);

    return () => window.clearInterval(timer);
  }, [frameCount, isPlaying]);

  if (!activeSnapshot) {
    return null;
  }

  return (
    <div className="evidence-context">
      <div className="context-insights">
        {context.insights.map((insight, index) => (
          <div className={`context-insight ${insight.tone}`} key={`${insight.tone}-${index}`}>
            <div className="context-insight-title">
              <strong>{insight.title}</strong>
              <span>{insight.source === "llm" ? "AI" : "Rule"}</span>
            </div>
            <p>{insight.description}</p>
          </div>
        ))}
      </div>

      <div className="context-summary">
        <MiniMetric label="아군 사망" value={`${context.summary.ally_deaths}`} />
        <MiniMetric label="적 사망" value={`${context.summary.enemy_deaths}`} />
        <MiniMetric label="시야 이벤트" value={`${context.summary.ally_ward_events}/${context.summary.enemy_ward_events}`} />
        <MiniMetric label="오브젝트" value={`${context.summary.objective_events}`} />
      </div>

      <div className="context-controls">
        <button
          aria-label={isPlaying ? "정지" : "재생"}
          className="icon-button"
          disabled={frameCount < 2}
          onClick={() => setIsPlaying((current) => !current)}
          type="button"
        >
          {isPlaying ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
        </button>
        <input
          aria-label="타임라인 프레임"
          max={Math.max(0, frameCount - 1)}
          min={0}
          onChange={(event) => {
            setIsPlaying(false);
            setFrameIndex(Number(event.target.value));
          }}
          type="range"
          value={activeIndex}
        />
        <span>{formatOffset(activeSnapshot.offset_seconds)}</span>
      </div>

      <div className="context-body">
        <ContextMiniMap
          assets={assets}
          context={context}
          snapshot={activeSnapshot}
        />
        <div className="context-side">
          <ObjectiveStateBoard state={activeSnapshot.objective_state} />
          <ContextEventLog
            anchorTimestamp={context.anchor_timestamp_ms}
            events={context.events}
            snapshot={activeSnapshot}
          />
        </div>
      </div>
    </div>
  );
}

function ObjectiveStateBoard({ state }: { state: EvidenceContextSnapshot["objective_state"] }) {
  return (
    <div className="objective-state">
      <strong>오브젝트 상태</strong>
      <div className="objective-row">
        <span>블루</span>
        <ObjectivePill label="용" value={state.blue_dragons} />
        <ObjectivePill label="전" value={state.blue_heralds} />
        <ObjectivePill label="바" value={state.blue_barons} />
        <ObjectivePill label="타" value={state.blue_towers} />
        <ObjectivePill label="억" value={state.blue_inhibitors} />
        <ObjectivePill label="유" value={state.blue_voidgrubs} />
        <ObjectivePill label="아" value={state.blue_atakhans} />
      </div>
      <div className="objective-row red">
        <span>레드</span>
        <ObjectivePill label="용" value={state.red_dragons} />
        <ObjectivePill label="전" value={state.red_heralds} />
        <ObjectivePill label="바" value={state.red_barons} />
        <ObjectivePill label="타" value={state.red_towers} />
        <ObjectivePill label="억" value={state.red_inhibitors} />
        <ObjectivePill label="유" value={state.red_voidgrubs} />
        <ObjectivePill label="아" value={state.red_atakhans} />
      </div>
    </div>
  );
}

function ObjectivePill({ label, value }: { label: string; value: number }) {
  return (
    <span className="objective-pill">
      {label} {value}
    </span>
  );
}

function ContextEventLog({
  anchorTimestamp,
  events,
  snapshot
}: {
  anchorTimestamp: number;
  events: EvidenceContextEvent[];
  snapshot: EvidenceContextSnapshot;
}) {
  if (events.length === 0) {
    return <p className="event-description">이 구간의 세부 로그가 부족합니다.</p>;
  }

  return (
    <div className="context-event-log">
      {events.map((event, index) => {
        const isActive = Math.abs(event.timestamp_ms - snapshot.timestamp_ms) <= 45_000;
        return (
          <div className={isActive ? "context-event is-active" : "context-event"} key={`${event.timestamp_ms}-${event.type}-${index}`}>
            <span className={`event-type-badge ${event.type}`}>
              <EventGlyph type={event.type} />
              {eventTypeLabel(event.type)}
            </span>
            <div>
              <strong>{event.title}</strong>
              <small>{formatOffset(Math.round((event.timestamp_ms - anchorTimestamp) / 1000))} · {teamLabel(event.team)}</small>
            </div>
          </div>
        );
      })}
    </div>
  );
}
