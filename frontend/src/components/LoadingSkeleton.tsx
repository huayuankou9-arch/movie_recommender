export function LoadingSkeleton({ className = "h-60 w-full" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-white/10 ${className}`} />;
}
