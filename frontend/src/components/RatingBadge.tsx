export function RatingBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) return null;
  return (
    <span
      className="rounded-full bg-gold/20 px-2 py-1 text-xs font-semibold text-gold"
      title="推荐模型分（用于排序，分数越高代表越推荐）"
    >
      Rec {score.toFixed(2)}
    </span>
  );
}
