"use client";

import { Activity, Database, Loader2, Search, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { getHealth, searchSummoner, SummonerLookupResponse, SystemHealth } from "@/lib/api";

type LookupState = "idle" | "loading" | "success" | "error";

export default function Home() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [lookupState, setLookupState] = useState<LookupState>("idle");
  const [lookup, setLookup] = useState<SummonerLookupResponse | null>(null);
  const [error, setError] = useState("");

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
    setLookupState("loading");
    setError("");
    setLookup(null);

    try {
      const data = await searchSummoner({ gameName, tagLine });
      setLookup(data);
      setLookupState("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lookup failed");
      setLookupState("error");
    }
  }

  const apiStatus = healthError ? "offline" : health?.status ?? "checking";
  const dbStatus = healthError ? "unknown" : health?.database ?? "checking";
  const riotStatus = healthError ? "unknown" : health?.riot_api ?? "checking";

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

        <section className="result-panel" aria-live="polite">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Profile</p>
              <h2>Lookup result</h2>
            </div>
          </div>

          {lookupState === "idle" && <EmptyResult />}
          {lookupState === "loading" && <p className="state-copy">Loading Riot profile data...</p>}
          {lookupState === "error" && <p className="error-copy">{error}</p>}
          {lookupState === "success" && lookup && (
            <div className="result-grid">
              <ResultItem label="Riot ID" value={`${lookup.account.game_name}#${lookup.account.tag_line}`} />
              <ResultItem label="Level" value={lookup.summoner.summoner_level?.toString() ?? "-"} />
              <ResultItem label="Platform" value={lookup.summoner.platform_routing.toUpperCase()} />
              <ResultItem label="PUUID" value={lookup.account.puuid} compact />
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

function EmptyResult() {
  return (
    <div className="empty-result">
      <Search size={28} aria-hidden="true" />
      <p>No summoner loaded</p>
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
