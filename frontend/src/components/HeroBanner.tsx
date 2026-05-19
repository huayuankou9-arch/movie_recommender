import { useRef } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { repairPoster } from "../api/client";
import { MovieCard as Movie } from "../types";

export function HeroBanner({ movie }: { movie: Movie | null }) {
  if (!movie) return null;
  const fallback = "https://placehold.co/1200x675?text=No+Backdrop";
  const repairTried = useRef(false);
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-panel"
    >
      <img
        src={movie.backdrop_url || movie.poster_url || fallback}
        alt={movie.title}
        className="h-[300px] w-full object-cover md:h-[440px]"
        onError={async (e) => {
          const t = e.currentTarget;
          if (repairTried.current) {
            if (t.src !== fallback) t.src = fallback;
            return;
          }
          repairTried.current = true;
          try {
            const fixed = await repairPoster(movie.movieId, t.src);
            if (fixed.backdrop_url && fixed.backdrop_url !== t.src) {
              t.src = fixed.backdrop_url;
              return;
            }
            if (fixed.poster_url && fixed.poster_url !== t.src) {
              t.src = fixed.poster_url;
              return;
            }
          } catch (_err) {
            // fall back below
          }
          t.src = fallback;
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/45 to-transparent" />
      <div className="absolute bottom-0 left-0 max-w-2xl space-y-3 p-5 md:p-8">
        <p className="inline-flex rounded-full bg-neon/20 px-3 py-1 text-xs text-neon">Top Pick For You</p>
        <h1 className="text-3xl font-bold md:text-5xl">{movie.title}</h1>
        <p className="text-sm text-slate-200 md:text-base">{movie.year} • {movie.genres}</p>
        <p className="line-clamp-3 text-sm text-slate-200 md:text-base">{movie.overview || "No overview available."}</p>
        <p className="text-sm text-cyan-200">推荐理由：{movie.reason || "混合模型推荐"}</p>
        <div className="flex gap-3">
          <Link to={`/movie/${movie.movieId}`} className="rounded-md bg-neon px-4 py-2 text-sm font-semibold text-ink">
            View Detail
          </Link>
          <Link to={`/similar?movieId=${movie.movieId}`} className="rounded-md border border-white/30 px-4 py-2 text-sm text-white">
            Similar Movies
          </Link>
        </div>
      </div>
    </motion.section>
  );
}
