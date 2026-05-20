import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { MovieCard as Movie } from "../types";
import { PLACEHOLDER_POSTER, sanitizeBackdropUrl, sanitizePosterUrl, sanitizeTitle } from "../utils/movie";

export function HeroBanner({ movie }: { movie: Movie | null }) {
  const safeBackdrop = sanitizeBackdropUrl(movie?.backdrop_url);
  const safePoster = sanitizePosterUrl(movie?.poster_url);
  const initialBg = useMemo(() => safeBackdrop || safePoster || "", [safeBackdrop, safePoster]);
  const [bgSrc, setBgSrc] = useState(initialBg);
  const [bgFailed, setBgFailed] = useState(false);

  useEffect(() => {
    setBgSrc(initialBg);
    setBgFailed(false);
  }, [movie?.movieId, initialBg]);

  if (!movie) return null;

  const title = sanitizeTitle(movie.title) || "Untitled";
  const hasBackdrop = Boolean(safeBackdrop);
  const hasPoster = Boolean(safePoster && safePoster !== PLACEHOLDER_POSTER);
  const reason = movie.evidence || movie.reason || "Blended from similar viewers, related titles, and story-level content signals.";
  const rating = typeof movie.rating_avg === "number" ? movie.rating_avg.toFixed(2) : "N/A";
  const ratingCount = typeof movie.rating_count === "number" ? movie.rating_count.toLocaleString() : "0";

  return (
    <motion.section
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: "easeOut" }}
      className="relative min-h-[520px] overflow-hidden rounded-[2rem] border border-white/10 bg-panel shadow-glow md:min-h-[620px]"
    >
      {bgSrc ? (
        <img
          src={bgSrc}
          alt={title}
          className={`absolute inset-0 h-full w-full object-cover ${!hasBackdrop && hasPoster ? "scale-110 blur-sm" : ""}`}
          onError={() => {
            if (bgFailed) return;
            setBgFailed(true);
            if (bgSrc !== safePoster && safePoster && safePoster !== PLACEHOLDER_POSTER) {
              setBgSrc(safePoster);
              return;
            }
            setBgSrc("");
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-r from-slate-950 via-slate-900 to-black" />
      )}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_74%_18%,rgba(0,224,255,0.22),transparent_28%),linear-gradient(90deg,rgba(0,0,0,0.94),rgba(0,0,0,0.58),rgba(0,0,0,0.16))]" />
      <div className="relative flex min-h-[520px] max-w-3xl flex-col justify-end gap-4 p-6 md:min-h-[620px] md:p-10">
        <p className="w-fit rounded-full border border-neon/30 bg-black/35 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-neon">
          Top Pick For You
        </p>
        <h2 className="text-4xl font-black leading-none tracking-tight text-white md:text-7xl">{title}</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-200">
          <span>{movie.year || "Unknown Year"}</span>
          <span className="text-slate-500">/</span>
          <span>{movie.genres || "Unknown Genre"}</span>
          <span className="text-slate-500">/</span>
          <span>{rating} from {ratingCount} ratings</span>
        </div>
        <p className="line-clamp-3 max-w-2xl text-sm leading-6 text-slate-200 md:text-base">
          {movie.overview || "No overview available."}
        </p>
        <p className="max-w-2xl text-sm text-cyan-100">{reason}</p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link to={`/movie/${movie.movieId}`} className="rounded-full bg-neon px-5 py-2 text-sm font-semibold text-ink transition hover:bg-white">
            View Detail
          </Link>
          <Link to={`/similar?movieId=${movie.movieId}`} className="rounded-full border border-white/30 bg-black/25 px-5 py-2 text-sm text-white transition hover:bg-white/10">
            Similar Movies
          </Link>
        </div>
      </div>
    </motion.section>
  );
}
