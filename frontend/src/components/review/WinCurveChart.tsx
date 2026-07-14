import { WinCurvePoint } from "@/lib/api";

export function WinCurveChart({ points, team }: { points: WinCurvePoint[]; team: "blue" | "red" }) {
  if (points.length < 2) {
    return <div className="timeline-chart is-empty">No chart data</div>;
  }

  const invert = team === "red";
  const label = invert ? "우리 팀 우세도 (규칙 기반 추정 · 검증 전)" : "블루팀 우세도";

  const width = 760;
  const height = 220;
  const padding = 28;
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;
  const maxMinute = Math.max(1, ...points.map((point) => point.minute));
  const midY = height - padding - 0.5 * chartHeight;

  const polylinePoints = points
    .map((point) => {
      const probability = invert ? 1 - point.blue_win_prob : point.blue_win_prob;
      const clamped = Math.max(0, Math.min(1, probability));
      const x = padding + (point.minute / maxMinute) * chartWidth;
      const y = height - padding - clamped * chartHeight;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <div className="timeline-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
        <line className="chart-zero" x1={padding} x2={width - padding} y1={midY} y2={midY} />
        <polyline className="chart-line" points={polylinePoints} />
        <text x={padding} y={22}>
          {label}
        </text>
        <text x={width - padding} y={padding + 4} textAnchor="end">
          100%
        </text>
        <text x={width - padding} y={midY - 7} textAnchor="end">
          50%
        </text>
        <text x={width - padding} y={height - padding} textAnchor="end">
          0%
        </text>
        <text x={width - padding} y={height - 8} textAnchor="end">
          {maxMinute}m
        </text>
      </svg>
    </div>
  );
}
