import { TimelineFrameFeature } from "@/lib/api";

function formatGoldDiff(value: number) {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const absolute = Math.abs(value);
  const amount = absolute >= 1000 ? `${(absolute / 1000).toFixed(1)}k` : absolute.toLocaleString();
  return `${sign}${amount}`;
}

export function TimelineChart({
  frames,
  team
}: {
  frames: TimelineFrameFeature[];
  team: "blue" | "red";
}) {
  if (frames.length < 2) {
    return <div className="timeline-chart is-empty">No chart data</div>;
  }

  const invert = team === "red";
  const width = 760;
  const height = 220;
  const padding = 28;
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;
  const diffs = frames.map((frame) => (invert ? -frame.gold_diff : frame.gold_diff));
  const minDiff = Math.min(0, ...diffs);
  const maxDiff = Math.max(0, ...diffs);
  const range = maxDiff - minDiff || 1;
  const maxMinute = Math.max(1, ...frames.map((frame) => frame.minute));
  const zeroY = height - padding - ((0 - minDiff) / range) * chartHeight;
  const latestDiff = diffs[diffs.length - 1];

  const points = frames
    .map((frame, index) => {
      const x = padding + (frame.minute / maxMinute) * chartWidth;
      const y = height - padding - ((diffs[index] - minDiff) / range) * chartHeight;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <div className="timeline-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="우리 팀 골드 우세도 흐름">
        <line className="chart-zero" x1={padding} x2={width - padding} y1={zeroY} y2={zeroY} />
        <polyline className="chart-line" points={points} style={{ stroke: "var(--gold)" }} />
        <text x={padding} y={22}>
          우리 팀 골드 우세도
        </text>
        <text x={width - padding} y={22} textAnchor="end">
          현재 {formatGoldDiff(latestDiff)}
        </text>
        <text x={width - padding} y={height - 8} textAnchor="end">
          {maxMinute}m
        </text>
      </svg>
    </div>
  );
}
