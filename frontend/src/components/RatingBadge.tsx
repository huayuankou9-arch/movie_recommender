export function RatingBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) return null;
  return (
    <span
      className="rounded-full bg-gold/15 px-2 py-1 text-xs font-semibold text-amber-200"
      title="Recommendation match score used for ranking. Higher means the model is more confident."
    >
      Match {score.toFixed(2)}
    </span>
  );
}
