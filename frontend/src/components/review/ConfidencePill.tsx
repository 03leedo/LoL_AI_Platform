import { ScoreConfidence } from "@/lib/api";

export function ConfidencePill({ confidence }: { confidence: ScoreConfidence }) {
  return <span className={`confidence-pill ${confidence}`}>{confidence}</span>;
}
