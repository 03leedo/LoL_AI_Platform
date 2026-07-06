"use client";

import {
  Activity,
  BarChart3,
  Database,
  Loader2,
  Search,
  ShieldCheck,
  Swords
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  getHealth,
  getMatchTimelineAnalysis,
  getRecentMatchIds,
  MatchTimelineAnalysisResponse,
  searchSummoner,
  SummonerLookupResponse,
  SystemHealth,
  TimelineFrameFeature
} from "@/lib/api";

type LoadState = "idle" | "loading" | "success" | "error";

const RECENT_MATCH_COUNT = 5;

export default function Home() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [lookupState, setLookupState] = useState<LoadState>("idle");
  const [lookup, setLookup] = useState<SummonerLookupResponse | null>(null);
  const [lookupError, setLookupError] = useState("");
  const [matchState, setMatchState] = useState<LoadState>("idle");
  const [matchIds, setMatchIds] = useState<string[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState("");
  const [matchError, setMatchError] = useState("");
  const [timelineState, setTimelineState] = useState<LoadState>("idle");
  const [timeline, setTimeline] = useState<MatchTimelineAnalysisResponse | null>(null);
  const [timelineError, setTimelineError] = useState("");

  useEffect(() => {
    getHealth()
      .then((data) => {
        setHealth(data);
        setHealthError(false);
      })
      .catch(() => {
        setHealthError(true);
      });
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedGameName = gameName.trim();
    const normalizedTagLine = tagLine.trim();

    setLookupState("loading");
    setLookupError("");
    setLookup(null);
    resetMatches();

    try {
      const data = await searchSummoner({
        gameName: normalizedGameName,
        tagLine: normalizedTagLine
      });
      setLookup(data);
      setLookupState("success");
    } catch (err) {
      setLookupError(err instanceof Error ? err.message : "Lookup failed");
      setLookupState("error");
      return;
    }

    setMatchState("loading");
    try {
      const matches = await getRecentMatchIds({
        gameName: normalizedGameName,
        tagLine: normalizedTagLine,
        count: RECENT_MATCH_COUNT
      });
      setMatchIds(matches.match_ids);
      setSelectedMatchId(matches.match_ids[0] ?? "");
      setMatchState("success");
    } catch (err) {
      setMatchError(err instanceof Error ? err.message : "Recent matches lookup failed");
      setMatchState("error");
    }
  }

  async function onAnalyzeTimeline() {
    if (!selectedMatchId) {
      return;
    }

    setTimelineState("loading");
    setTimelineError("");
    setTimeline(null);

    try {
      const data = await getMatchTimelineAnalysis(selectedMatchId);
      setTimeline(data);
      setTimelineState("success");
    } catch (err) {
      setTimelineError(err instanceof Error ? err.message : "Timeline analysis failed");
      setTimelineState("error");
    }
  }

  function onSelectMatch(matchId: string) {
    setSelectedMatchId(matchId);
    setTimelineState("idle");
    setTimeline(null);
    setTimelineError("");
  }

  function resetMatches() {
    setMatchState("idle");
    setMatchIds([]);
    setSelectedMatchId("");
    setMatchError("");
    setTimelineState("idle");
    setTimeline(null);
    setTimelineError("");
  }

  const apiStatus = healthError ? "offline" : health?.status ?? "checking";
  const dbStatus = healthError ? "unknown" : health?.database ?? "checking";
  const riotStatus = healthError ? "unknown" : health?.riot_api ?? "checking";
  const latestFrame = timeline?.frames[timeline.frames.length - 1];

  return (
    <main className="workspace">
      <header className="topbar">
        <div>
          <p className="eyebrow">LoL AI Platform</p>
          <h1>Match intelligence workspace</h1>
        </div>
        <div className={`system-pill ${apiStatus === "ok" ? "is-ok" : ""}`}>
          <Activity size={18} aria-hidden="true" />
          <span>API {apiStatus}</span>
        </div>
      </header>

      <section className="control-grid">
        <form className="lookup-panel" onSubmit={onSubmit}>
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Riot ID</p>
              <h2>Summoner lookup</h2>
            </div>
            <ShieldCheck size={22} aria-hidden="true" />
          </div>

          <label htmlFor="gameName">Game name</label>
          <input
            id="gameName"
            name="gameName"
            value={gameName}
            onChange={(event) => setGameName(event.target.value)}
            placeholder="Hide on bush"
            autoComplete="off"
            required
          />

          <label htmlFor="tagLine">Tag line</label>
          <input
            id="tagLine"
            name="tagLine"
            value={tagLine}
            onChange={(event) => setTagLine(event.target.value)}
            placeholder="KR1"
            autoComplete="off"
            required
          />

          <button type="submit" disabled={lookupState === "loading"}>
            {lookupState === "loading" ? (
              <Loader2 className="spin" size={18} aria-hidden="true" />
            ) : (
              <Search size={18} aria-hidden="true" />
            )}
            <span>Search summoner</span>
          </button>
        </form>

        <section className="status-panel" aria-label="System status">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Local stack</p>
              <h2>Service state</h2>
            </div>
            <Database size={22} aria-hidden="true" />
          </div>

          <div className="metric-list">
            <StatusRow label="Backend" value={apiStatus} tone={apiStatus === "ok" ? "good" : "warn"} />
            <StatusRow label="Database" value={dbStatus} tone={dbStatus === "ok" ? "good" : "warn"} />
            <StatusRow
              label="Riot key"
              value={riotStatus}
              tone={riotStatus === "configured" ? "good" : "warn"}
            />
          </div>

          <div className="lane-strip" aria-hidden="true">
            <span className="lane lane-blue" />
            <span className="lane lane-rust" />
            <span className="lane lane-green" />
          </div>
        </section>

        <section className="match-panel" aria-live="polite">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Match-V5</p>
              <h2>Recent matches</h2>
            </div>
            <Swords size={22} aria-hidden="true" />
          </div>

          {matchState === "idle" && <EmptyResult icon="search" label="No matches loaded" />}
          {matchState === "loading" && <p className="state-copy">Loading recent matches...</p>}
          {matchState === "error" && <p className="error-copy">{matchError}</p>}
          {matchState === "success" && matchIds.length === 0 && (
            <EmptyResult icon="search" label="No recent matches found" />
          )}
          {matchState === "success" && matchIds.length > 0 && (
            <div className="match-picker">
              <label htmlFor="matchId">Match ID</label>
              <select
                id="matchId"
                value={selectedMatchId}
                onChange={(event) => onSelectMatch(event.target.value)}
              >
                {matchIds.map((matchId) => (
                  <option key={matchId} value={matchId}>
                    {matchId}
                  </option>
                ))}
              </select>
              <button type="button" onClick={onAnalyzeTimeline} disabled={timelineState === "loading"}>
                {timelineState === "loading" ? (
                  <Loader2 className="spin" size={18} aria-hidden="true" />
                ) : (
                  <BarChart3 size={18} aria-hidden="true" />
                )}
                <span>Analyze timeline</span>
              </button>
            </div>
          )}
        </section>

        <section className="result-panel" aria-live="polite">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Profile</p>
              <h2>Lookup result</h2>
            </div>
          </div>

          {lookupState === "idle" && <EmptyResult icon="search" label="No summoner loaded" />}
          {lookupState === "loading" && <p className="state-copy">Loading Riot profile data...</p>}
          {lookupState === "error" && <p className="error-copy">{lookupError}</p>}
          {lookupState === "success" && lookup && (
            <div className="result-grid">
              <ResultItem label="Riot ID" value={`${lookup.account.game_name}#${lookup.account.tag_line}`} />
              <ResultItem label="Level" value={lookup.summoner.summoner_level?.toString() ?? "-"} />
              <ResultItem label="Platform" value={lookup.summoner.platform_routing.toUpperCase()} />
              <ResultItem label="PUUID" value={lookup.account.puuid} compact />
            </div>
          )}
        </section>

        <section className="analysis-panel" aria-live="polite">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Timeline analytics</p>
              <h2>Gold and objective flow</h2>
            </div>
            <BarChart3 size={22} aria-hidden="true" />
          </div>

          {timelineState === "idle" && <EmptyResult icon="chart" label="No timeline loaded" />}
          {timelineState === "loading" && <p className="state-copy">Analyzing match timeline...</p>}
          {timelineState === "error" && <p className="error-copy">{timelineError}</p>}
          {timelineState === "success" && timeline && latestFrame && (
            <div className="analysis-stack">
              <div className="analysis-grid">
                <ResultItem label="Frames" value={timeline.frame_count.toString()} />
                <ResultItem label="Gold diff" value={formatDiff(latestFrame.gold_diff)} />
                <ResultItem label="XP diff" value={formatDiff(latestFrame.xp_diff)} />
                <ResultItem label="CS diff" value={formatDiff(latestFrame.cs_diff)} />
                <ResultItem
                  label="Dragons"
                  value={`${latestFrame.blue_dragon_kills} - ${latestFrame.red_dragon_kills}`}
                />
                <ResultItem
                  label="Towers"
                  value={`${latestFrame.blue_tower_kills} - ${latestFrame.red_tower_kills}`}
                />
              </div>
              <TimelineChart frames={timeline.frames} />
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

function StatusRow({
  label,
  value,
  tone
}: {
  label: string;
  value: string;
  tone: "good" | "warn";
}) {
  return (
    <div className="status-row">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );
}

function EmptyResult({ icon, label }: { icon: "chart" | "search"; label: string }) {
  const Icon = icon === "chart" ? BarChart3 : Search;

  return (
    <div className="empty-result">
      <Icon size={28} aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

function ResultItem({
  label,
  value,
  compact = false
}: {
  label: string;
  value: string;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "result-item compact" : "result-item"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TimelineChart({ frames }: { frames: TimelineFrameFeature[] }) {
  if (frames.length < 2) {
    return <div className="timeline-chart is-empty">No chart data</div>;
  }

  const width = 760;
  const height = 240;
  const padding = 28;
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;
  const diffs = frames.map((frame) => frame.gold_diff);
  const minDiff = Math.min(0, ...diffs);
  const maxDiff = Math.max(0, ...diffs);
  const range = maxDiff - minDiff || 1;
  const maxMinute = Math.max(1, ...frames.map((frame) => frame.minute));
  const zeroY = height - padding - ((0 - minDiff) / range) * chartHeight;

  const points = frames
    .map((frame) => {
      const x = padding + (frame.minute / maxMinute) * chartWidth;
      const y = height - padding - ((frame.gold_diff - minDiff) / range) * chartHeight;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const lastFrame = frames[frames.length - 1];

  return (
    <div className="timeline-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Gold difference over time">
        <line className="chart-zero" x1={padding} x2={width - padding} y1={zeroY} y2={zeroY} />
        <polyline className="chart-line" points={points} />
        <circle
          className="chart-endpoint"
          cx={padding + (lastFrame.minute / maxMinute) * chartWidth}
          cy={height - padding - ((lastFrame.gold_diff - minDiff) / range) * chartHeight}
          r="5"
        />
        <text x={padding} y={22}>
          Blue gold diff
        </text>
        <text x={width - padding} y={height - 8} textAnchor="end">
          {maxMinute}m
        </text>
      </svg>
    </div>
  );
}

function formatDiff(value: number) {
  if (value > 0) {
    return `+${value.toLocaleString()}`;
  }
  return value.toLocaleString();
}
