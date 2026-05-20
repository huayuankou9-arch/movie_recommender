import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { BookmarkPlus } from "lucide-react";
import { MovieCard as Movie } from "../types";
import { PLACEHOLDER_POSTER, sanitizePosterUrl, sanitizeTitle } from "../utils/movie";
import { GenreBadge } from "./GenreBadge";
import { RatingBadge } from "./RatingBadge";
import { ReasonTooltip } from "./ReasonTooltip";

export function MovieCard({ movie }: { movie: Movie }) {
  const [posterSrc, setPosterSrc] = useState(sanitizePosterUrl(movie.poster_url));
  const [posterFailed, setPosterFailed] = useState(false);
  useEffect(() => {
    setPosterSrc(sanitizePosterUrl(movie.poster_url));
    setPosterFailed(false);
  }, [movie.movieId, movie.poster_url]);

  const genres = movie.genres?.split(",").map((g) => g.trim()).filter(Boolean).slice(0, 2) ?? [];
  const title = sanitizeTitle(movie.title) || "Untitled";
  const ratingText =
    typeof movie.rating_avg === "number" && typeof movie.rating_count === "number"
      ? `Avg ${movie.rating_avg.toFixed(2)} · ${movie.rating_count} ratings`
      : "";

  return (
    <motion.article
      whileHover={{ scale: 1.05, y: -4 }}
      transition={{ type: "spring", stiffness: 180, damping: 22 }}
      className="group relative min-w-[180px] max-w-[180px] overflow-hidden rounded-xl border border-white/10 bg-panel shadow-glow transition-colors duration-300 hover:border-neon/30 md:min-w-[220px] md:max-w-[220px]"
    >
      <img
        src={posterSrc}
        alt={title}
        className="h-[260px] w-full object-cover md:h-[320px]"
        loading="lazy"
        onError={(e) => {
          if (posterFailed) return;
          setPosterFailed(true);
          setPosterSrc(PLACEHOLDER_POSTER);
          e.currentTarget.src = PLACEHOLDER_POSTER;
        }}
      />
      <div className="space-y-2 p-3">
        <p className="line-clamp-1 text-sm font-semibold">{title}</p>
        <div className="flex flex-wrap gap-1">
          {genres.map((g) => (
            <GenreBadge key={g} text={g} />
          ))}
          <RatingBadge score={movie.score} />
        </div>
        {ratingText && <p className="line-clamp-1 text-[11px] text-slate-400">{ratingText}</p>}
        <ReasonTooltip movie={movie} />
      </div>
      <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/90 via-black/20 to-transparent p-3 opacity-0 transition group-hover:opacity-100">
        <p className="mb-3 line-clamp-3 text-xs text-slate-200">{movie.overview || "No overview available."}</p>
        {movie.review_snippet && <p className="mb-3 line-clamp-2 text-xs text-cyan-100">{movie.review_snippet}</p>}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link to={`/movie/${movie.movieId}`} className="rounded-md bg-neon/20 px-2 py-1 text-neon">
            View Detail
          </Link>
          <Link to={`/similar?movieId=${movie.movieId}`} className="rounded-md bg-coral/20 px-2 py-1 text-coral">
            Similar
          </Link>
          <button className="inline-flex items-center gap-1 rounded-md bg-white/10 px-2 py-1 text-white" title="Save to watchlist">
            <BookmarkPlus size={13} />
            Save
          </button>
        </div>
      </div>
    </motion.article>
  );
}
