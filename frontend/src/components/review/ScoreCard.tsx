import { ConfidencePill } from "@/components/review/ConfidencePill";
import { PlayerAnalysisScore } from "@/lib/api";

export function ScoreCard({
  label,
  score,
  sublabel
}: {
  label: string;
  score: PlayerAnalysisScore;
  sublabel?: string;
}) {
  return (
    <div className={score.direction === "higher_is_worse" ? "score-card is-risk" : "score-card"} title={sublabel}>
      <span>{label}</span>
      <strong>{score.value === null ? "N/A" : score.value}</strong>
      <ConfidencePill confidence={score.confidence} />
    </div>
  );
}
