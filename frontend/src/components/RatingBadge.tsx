export function RatingBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) return null;
  return (
    <span className="rounded-full bg-gold/20 px-2 py-1 text-xs font-semibold text-gold">
      {score.toFixed(2)}
    </span>
  );
}
