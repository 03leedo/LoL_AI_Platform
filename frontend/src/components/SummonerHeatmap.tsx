"use client";

import { MapPin } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { LoadingState } from "@/components/StatusViews";
import { getSummonerHeatmap, SummonerHeatmapResponse } from "@/lib/api";
import { mapCoord, mapImageUrl } from "@/lib/assets";
import { LoadState } from "@/lib/types";

const HEATMAP_MATCH_COUNT = 10;
const SUMMONERS_RIFT_MAP_ID = 11;

const ZONE_LABELS: Record<string, string> = {
  top: "탑",
  mid: "미드",
  bot: "봇",
  ally_jungle: "아군 정글",
  enemy_jungle: "적 정글"
};

type DotView = "deaths" | "kills" | "all";

function zoneLabel(zone: string) {
  return ZONE_LABELS[zone] ?? zone;
}

function formatShare(share: number) {
  const percent = share <= 1 ? share * 100 : share;
  return `${Math.round(percent)}%`;
}

export function SummonerHeatmap({ gameName, tagLine }: { gameName: string; tagLine: string }) {
  const [heatmapState, setHeatmapState] = useState<LoadState>("idle");
  const [heatmap, setHeatmap] = useState<SummonerHeatmapResponse | null>(null);
  const [heatmapError, setHeatmapError] = useState("");
  const [dotView, setDotView] = useState<DotView>("deaths");
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  async function analyze() {
    setHeatmapState("loading");
    setHeatmapError("");

    try {
      const data = await getSummonerHeatmap(gameName, tagLine, HEATMAP_MATCH_COUNT);
      if (!mountedRef.current) {
        return;
      }
      setHeatmap(data);
      setDotView("deaths");
      setHeatmapState("success");
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      setHeatmapError(err instanceof Error ? err.message : "킬/데스 히트맵 분석에 실패했습니다.");
      setHeatmapState("error");
    }
  }

  const deathZones = heatmap?.death_zones ?? [];
  const dangerZones = deathZones.filter((zone) => zone.is_death_zone);
  const showKills = dotView === "kills" || dotView === "all";
  const showDeaths = dotView === "deaths" || dotView === "all";

  return (
    <section className="history-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Position insight</p>
          <h2>킬/데스 히트맵</h2>
        </div>
        <MapPin size={22} aria-hidden="true" />
      </div>

      {heatmapState === "idle" && (
        <div className="heatmap-idle">
          <button onClick={analyze} type="button">
            최근 10경기 분석하기
          </button>
          <p>처음 분석은 최대 1분 정도 걸릴 수 있어요.</p>
        </div>
      )}

      {heatmapState === "loading" && (
        <LoadingState label="최근 경기의 킬/데스 위치를 수집하는 중입니다. 처음 분석은 최대 1분 정도 걸릴 수 있어요." />
      )}

      {heatmapState === "error" && (
        <div className="heatmap-idle">
          <p className="error-copy">{heatmapError}</p>
          <button onClick={analyze} type="button">
            다시 시도
          </button>
        </div>
      )}

      {heatmapState === "success" && heatmap && (
        <div className="heatmap-body">
          <div className="heatmap-toolbar">
            <div aria-label="히트맵 표시 항목" className="heatmap-toggle" role="group">
              <button
                className={dotView === "deaths" ? "is-active" : ""}
                onClick={() => setDotView("deaths")}
                type="button"
              >
                데스
              </button>
              <button
                className={dotView === "kills" ? "is-active" : ""}
                onClick={() => setDotView("kills")}
                type="button"
              >
                킬
              </button>
              <button
                className={dotView === "all" ? "is-active" : ""}
                onClick={() => setDotView("all")}
                type="button"
              >
                전체
              </button>
            </div>
            <span className="heatmap-meta">
              {heatmap.matches_analyzed}/{heatmap.matches_requested} 경기 분석됨
            </span>
          </div>

          <div className="context-body">
            <div
              aria-label="최근 경기 킬/데스 위치 미니맵"
              className="context-map"
              role="img"
              style={{ backgroundImage: `url(${mapImageUrl(SUMMONERS_RIFT_MAP_ID)})` }}
            >
              <span className="map-overlay" />
              {showKills &&
                heatmap.kills.map((point, index) => (
                  <span
                    className="heatmap-dot is-kill"
                    key={`kill-${point.match_id}-${index}`}
                    style={{
                      left: `${mapCoord(point.x)}%`,
                      top: `${100 - mapCoord(point.y)}%`
                    }}
                    title={`킬 · ${point.minute}분 · ${zoneLabel(point.zone)}`}
                  />
                ))}
              {showDeaths &&
                heatmap.deaths.map((point, index) => (
                  <span
                    className="heatmap-dot"
                    key={`death-${point.match_id}-${index}`}
                    style={{
                      left: `${mapCoord(point.x)}%`,
                      top: `${100 - mapCoord(point.y)}%`
                    }}
                    title={`데스 · ${point.minute}분 · ${zoneLabel(point.zone)}`}
                  />
                ))}
            </div>

            <div className="context-side">
              {dangerZones.map((zone) => (
                <p className="heatmap-callout" key={`callout-${zone.zone}`}>
                  데스 존: 최근 {heatmap.matches_analyzed}경기 데스의 {formatShare(zone.share)}가 &apos;
                  {zoneLabel(zone.zone)}&apos;에서 발생했어요.
                </p>
              ))}

              {deathZones.length > 0 && (
                <div className="zone-chips">
                  {deathZones.map((zone) => (
                    <span className={zone.is_death_zone ? "zone-chip is-danger" : "zone-chip"} key={zone.zone}>
                      {zoneLabel(zone.zone)} <strong>{zone.count}회</strong> ({formatShare(zone.share)})
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
