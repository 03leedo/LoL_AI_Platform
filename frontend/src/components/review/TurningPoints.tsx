import { MatchTurningPoint } from "@/lib/api";

const FALLBACK_TITLE = "골드·오브젝트 흐름 급변";

function formatDelta(delta: number) {
  const points = Math.round(delta * 100);
  return `${points > 0 ? "+" : ""}${points}%p`;
}

export function TurningPoints({ points }: { points: MatchTurningPoint[] }) {
  if (points.length === 0) {
    return null;
  }

  return (
    <div className="turning-points-section">
      <h3>이 판의 변곡점</h3>
      <div className="turning-point-list">
        {points.map((point, index) => {
          const isPositive = Math.round(point.delta * 100) >= 0;
          const before = Math.round(point.prob_before * 100);
          const after = Math.round(point.prob_after * 100);

          return (
            <div className="turning-point" key={`${point.minute}-${index}`}>
              <span className="evidence-minute">{point.minute}분</span>
              <div className="turning-point-body">
                <div className="turning-point-head">
                  <strong>{point.title ?? FALLBACK_TITLE}</strong>
                  <span
                    className={
                      isPositive ? "turning-delta is-positive" : "turning-delta is-negative"
                    }
                  >
                    {formatDelta(point.delta)}
                  </span>
                </div>
                <p className="turning-point-prob">
                  우세도 {before}% → {after}%
                </p>
                {point.description && <p className="turning-point-desc">{point.description}</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
