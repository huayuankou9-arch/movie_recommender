export function ReasonTooltip({ reason }: { reason?: string }) {
  if (!reason) return null;
  return (
    <span
      className="line-clamp-2 max-w-full rounded-md border border-neon/30 bg-neon/10 px-2 py-1 text-[11px] text-cyan-200"
      title={reason}
    >
      {reason}
    </span>
  );
}
