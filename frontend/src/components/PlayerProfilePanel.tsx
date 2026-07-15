"use client";

import { ChevronDown, ChevronUp, Radar } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { LoadingState } from "@/components/StatusViews";
import { ConfidencePill } from "@/components/review/ConfidencePill";
import { getPlayerProfile, PlayerProfileResponse, ProfileDimension, ProfileSubmetric } from "@/lib/api";
import { formatRole } from "@/lib/format";
import { LoadState } from "@/lib/types";

const PROFILE_WINDOW = 20;

const RATIO_SUBMETRIC_KEYS = new Set(["kill_participation", "team_damage_share", "lane_advantage_rate"]);

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, value));
}

function formatSubmetricValue(submetric: ProfileSubmetric) {
  if (submetric.value === null) {
    return "-";
  }
  if (RATIO_SUBMETRIC_KEYS.has(submetric.key) && Math.abs(submetric.value) <= 1) {
    return `${Math.round(submetric.value * 100)}%`;
  }
  return Math.abs(submetric.value) >= 10 ? submetric.value.toFixed(1) : submetric.value.toFixed(2);
}

export function PlayerProfilePanel({ gameName, tagLine }: { gameName: string; tagLine: string }) {
  const [profileState, setProfileState] = useState<LoadState>("loading");
  const [profile, setProfile] = useState<PlayerProfileResponse | null>(null);
  const [profileError, setProfileError] = useState("");
  const [selectedRole, setSelectedRole] = useState<string | undefined>(undefined);
  const [availableRoles, setAvailableRoles] = useState<string[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({});
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadProfile = useCallback(
    async (role?: string) => {
      setProfileState("loading");
      setProfileError("");

      try {
        const data = await getPlayerProfile(gameName, tagLine, PROFILE_WINDOW, role);
        if (!mountedRef.current) {
          return;
        }
        setProfile(data);
        setAvailableRoles(data.available_roles);
        setExpandedKeys({});
        setProfileState("success");
      } catch (err) {
        if (!mountedRef.current) {
          return;
        }
        setProfileError(err instanceof Error ? err.message : "퍼포먼스 프로필을 불러오지 못했습니다.");
        setProfileState("error");
      }
    },
    [gameName, tagLine]
  );

  useEffect(() => {
    setSelectedRole(undefined);
    setAvailableRoles([]);
    setProfile(null);
    loadProfile(undefined);
  }, [loadProfile]);

  const activeRole = selectedRole ?? profile?.role ?? null;

  function onSelectRole(role: string) {
    if (role === activeRole && profileState === "success") {
      return;
    }
    setSelectedRole(role);
    loadProfile(role);
  }

  function toggleDimension(key: string) {
    setExpandedKeys((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <section className="history-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Performance profile</p>
          <h2>퍼포먼스 프로필</h2>
        </div>
        <Radar size={22} aria-hidden="true" />
      </div>

      <div className="profile-panel-body">
        {availableRoles.length > 0 && (
          <div className="heatmap-toggle profile-role-chips">
            {availableRoles.map((role) => (
              <button
                className={role === activeRole ? "is-active" : ""}
                disabled={profileState === "loading"}
                key={role}
                onClick={() => onSelectRole(role)}
                type="button"
              >
                {formatRole(role)}
              </button>
            ))}
          </div>
        )}

        {profileState === "loading" && <LoadingState label="퍼포먼스 프로필을 불러오는 중입니다." />}

        {profileState === "error" && (
          <div className="heatmap-idle">
            <p className="error-copy">{profileError}</p>
            <button onClick={() => loadProfile(selectedRole)} type="button">
              다시 시도
            </button>
          </div>
        )}

        {profileState === "success" && profile && profile.insufficient_data && (
          <div className="heatmap-idle">
            <p>프로필을 만들기엔 해당 포지션 표본이 부족해요. 랭크 분석에서 경기를 수집해 주세요.</p>
          </div>
        )}

        {profileState === "success" && profile && !profile.insufficient_data && (
          <>
            <div>
              <p className="profile-meta">
                {formatRole(profile.role)} · 최근 솔로랭크 {profile.games}경기
              </p>
              <p className="profile-meta-sub">{profile.comparison_group}</p>
            </div>

            <div className="profile-dimension-grid">
              {profile.dimensions.map((dimension) => (
                <ProfileDimensionCard
                  dimension={dimension}
                  isExpanded={Boolean(expandedKeys[dimension.key])}
                  key={dimension.key}
                  onToggle={() => toggleDimension(dimension.key)}
                />
              ))}
            </div>

            <p className="rank-footnote">
              프로필은 최근 관측 요약이며 고정 실력이 아닙니다 · 백분위는 로컬 수집 표본 기준입니다.
            </p>
          </>
        )}
      </div>
    </section>
  );
}

function ProfileDimensionCard({
  dimension,
  isExpanded,
  onToggle
}: {
  dimension: ProfileDimension;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const score = dimension.score;
  const rawScore = dimension.raw_score;
  const showRawNote = score !== null && rawScore !== null && Math.abs(rawScore - score) > 2;

  return (
    <div className="profile-dimension-card">
      <div className="profile-dim-head">
        <span className="profile-dim-label">{dimension.label}</span>
        <ConfidencePill confidence={dimension.confidence} />
      </div>

      <p className="profile-dim-score">
        {score === null ? (
          <span className="is-na">N/A (표본 부족)</span>
        ) : (
          <>
            <strong>{Math.round(score)}</strong>
            <span>점</span>
          </>
        )}
      </p>

      {showRawNote && rawScore !== null && (
        <p className="profile-raw-note">표본 보정 전 {Math.round(rawScore)}점</p>
      )}

      {dimension.percentile !== null ? (
        <div className="profile-percentile">
          <span aria-hidden="true" className="ability-bar">
            <span
              className="ability-bar-fill"
              style={{ width: `${clampPercent(dimension.percentile)}%` }}
            />
          </span>
          <span className="profile-percentile-label">
            동일 표본 대비 백분위 {Math.round(dimension.percentile)}
          </span>
        </div>
      ) : (
        <p className="profile-percentile-empty">백분위 없음 (비교 표본 부족)</p>
      )}

      <button
        aria-expanded={isExpanded}
        className="profile-detail-toggle"
        onClick={onToggle}
        type="button"
      >
        자세히
        {isExpanded ? (
          <ChevronUp size={14} aria-hidden="true" />
        ) : (
          <ChevronDown size={14} aria-hidden="true" />
        )}
      </button>

      {isExpanded && (
        <div className="profile-submetric-list">
          {dimension.submetrics.map((submetric) => (
            <div className="profile-submetric-row" key={submetric.key}>
              <span className="profile-submetric-label">
                {submetric.label}
                {submetric.lower_is_better && (
                  <span className="profile-submetric-note"> (낮을수록 좋음)</span>
                )}
              </span>
              <span className="profile-submetric-data">
                <span className="profile-submetric-value">{formatSubmetricValue(submetric)}</span>
                {submetric.percentile !== null && (
                  <span className="profile-submetric-pct">
                    백분위 {Math.round(submetric.percentile)}
                  </span>
                )}
              </span>
            </div>
          ))}
          <p className="profile-evidence-footer">근거 {dimension.evidence_match_ids.length}경기</p>
        </div>
      )}
    </div>
  );
}
