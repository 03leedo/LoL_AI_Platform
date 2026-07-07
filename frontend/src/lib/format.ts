import { TeamSide } from "@/lib/api";

export function eventTypeLabel(type: string) {
  const labels: Record<string, string> = {
    kill: "킬",
    dragon: "드래곤",
    herald: "전령",
    baron: "바론",
    voidgrub: "유충",
    atakhan: "아타칸",
    tower: "타워",
    inhibitor: "억제기",
    ward_placed: "와드",
    ward_killed: "와드 제거"
  };
  return labels[type] ?? "사건";
}

export function teamLabel(team: TeamSide) {
  const labels = {
    blue: "블루 팀",
    red: "레드 팀",
    neutral: "중립"
  };
  return labels[team];
}

export function formatOffset(seconds: number) {
  if (seconds === 0) {
    return "0s";
  }
  return `${seconds > 0 ? "+" : ""}${seconds}s`;
}

export function queueLabel(queueId: number | null) {
  const labels: Record<number, string> = {
    420: "솔로랭크",
    430: "일반",
    440: "자유랭크",
    450: "칼바람",
    490: "빠른대전"
  };
  return queueId ? labels[queueId] ?? `Queue ${queueId}` : "게임";
}

export function formatRole(role: string | null) {
  const labels: Record<string, string> = {
    TOP: "탑",
    JUNGLE: "정글",
    MIDDLE: "미드",
    MID: "미드",
    BOTTOM: "원딜",
    ADC: "원딜",
    UTILITY: "서포터",
    SUPPORT: "서포터"
  };
  if (!role) {
    return "-";
  }
  return labels[role.toUpperCase()] ?? role;
}

export function formatDuration(seconds: number | null) {
  if (!seconds) {
    return "-";
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}

export function formatCsPerMinute(cs: number, seconds: number | null) {
  if (!seconds) {
    return "-";
  }
  return (cs / (seconds / 60)).toFixed(1);
}

export function formatKda(kills: number | null, deaths: number | null, assists: number | null) {
  const deathCount = deaths ?? 0;
  if (deathCount === 0) {
    return "Perfect";
  }
  return `${(((kills ?? 0) + (assists ?? 0)) / deathCount).toFixed(2)} KDA`;
}

export function formatCompactNumber(value: number | null) {
  if (value === null) {
    return "-";
  }
  if (Math.abs(value) >= 1000) {
    const rounded = value >= 10_000 ? (value / 1000).toFixed(0) : (value / 1000).toFixed(1);
    return `${rounded}k`;
  }
  return value.toLocaleString();
}

export function formatPercent(value: number | null) {
  if (value === null) {
    return "-";
  }
  return `${value}%`;
}

export function formatGameTime(timestamp: number | null) {
  if (!timestamp) {
    return "-";
  }
  const date = new Date(timestamp);
  const diffMs = Date.now() - date.getTime();
  const diffHours = Math.floor(diffMs / 3_600_000);
  if (diffHours < 1) {
    return "방금 전";
  }
  if (diffHours < 24) {
    return `${diffHours}시간 전`;
  }
  return `${Math.floor(diffHours / 24)}일 전`;
}

export function formatDiff(value: number) {
  if (value > 0) {
    return `+${value.toLocaleString()}`;
  }
  return value.toLocaleString();
}
