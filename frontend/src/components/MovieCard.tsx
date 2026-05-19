import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { MovieCard as Movie } from "../types";
import { GenreBadge } from "./GenreBadge";
import { RatingBadge } from "./RatingBadge";
import { ReasonTooltip } from "./ReasonTooltip";

export function MovieCard({ movie }: { movie: Movie }) {
  const posterFallback = "/placeholder-poster.png";
  const genres = movie.genres?.split(",").map((g) => g.trim()).filter(Boolean).slice(0, 2) ?? [];
  return (
    <motion.article
      whileHover={{ scale: 1.05, y: -4 }}
      transition={{ type: "spring", stiffness: 220, damping: 20 }}
      className="group relative min-w-[180px] max-w-[180px] overflow-hidden rounded-xl border border-white/10 bg-panel shadow-glow md:min-w-[220px] md:max-w-[220px]"
    >
      <img
        src={movie.poster_url || posterFallback}
        alt={movie.title}
        className="h-[260px] w-full object-cover md:h-[320px]"
        onError={(e) => {
          const t = e.currentTarget;
          t.src = posterFallback;
        }}
      />
      <div className="space-y-2 p-3">
        <p className="line-clamp-1 text-sm font-semibold">{movie.title}</p>
        <div className="flex flex-wrap gap-1">
          {genres.map((g) => (
            <GenreBadge key={g} text={g} />
          ))}
          <RatingBadge score={movie.score} />
        </div>
        <ReasonTooltip reason={movie.reason} />
      </div>
      <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/90 via-black/20 to-transparent p-3 opacity-0 transition group-hover:opacity-100">
        <p className="mb-3 line-clamp-3 text-xs text-slate-200">{movie.overview || "No overview available."}</p>
        <div className="flex gap-2 text-xs">
          <Link to={`/movie/${movie.movieId}`} className="rounded-md bg-neon/20 px-2 py-1 text-neon">
            View Detail
          </Link>
          <Link to={`/similar?movieId=${movie.movieId}`} className="rounded-md bg-coral/20 px-2 py-1 text-coral">
            Similar
          </Link>
        </div>
      </div>
    </motion.article>
  );
}
