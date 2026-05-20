import { BookmarkPlus, Check, Heart, ThumbsDown } from "lucide-react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { MovieCard as Movie } from "../types";
import { getMovieState, removeMovie, toggleMovie } from "../utils/library";
import { PLACEHOLDER_POSTER, sanitizePosterUrl, sanitizeTitle } from "../utils/movie";
import { GenreBadge } from "./GenreBadge";
import { RatingBadge } from "./RatingBadge";
import { ReasonTooltip } from "./ReasonTooltip";

function reasonTypeLabel(type?: string) {
  const key = (type || "").toLowerCase();
  if (key.includes("popular")) return "Trending";
  if (key.includes("user")) return "Similar Users";
  if (key.includes("item")) return "Because You Watched";
  if (key.includes("predict") || key.includes("mf")) return "Predicted Match";
  if (key.includes("content") || key.includes("story")) return "Similar Story";
  if (key.includes("hybrid")) return "Best Match";
  return "Best Match";
}

function ActionButton({ active, label, activeLabel, onClick, children }: { active: boolean; label: string; activeLabel: string; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition ${
        active
          ? "border-neon/50 bg-neon/20 text-neon"
          : "border-white/10 bg-white/10 text-slate-100 hover:border-white/30 hover:bg-white/20"
      }`}
      title={active ? activeLabel : label}
    >
      {children}
      {active ? activeLabel : label}
    </button>
  );
}

export function MovieCard({ movie }: { movie: Movie }) {
  const [posterSrc, setPosterSrc] = useState(sanitizePosterUrl(movie.poster_url));
  const [posterFailed, setPosterFailed] = useState(false);
  const [state, setState] = useState(() => getMovieState(movie.movieId));
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    setPosterSrc(sanitizePosterUrl(movie.poster_url));
    setPosterFailed(false);
    setState(getMovieState(movie.movieId));
    setFeedback("");
  }, [movie.movieId, movie.poster_url]);

  const updateAction = (type: "liked" | "disliked" | "watchlisted") => {
    const key = type === "liked" ? "liked" : type === "disliked" ? "disliked" : "watchlist";
    const active = toggleMovie(key, movie);
    if (active && type === "liked") removeMovie("disliked", movie.movieId);
    if (active && type === "disliked") removeMovie("liked", movie.movieId);
    const next = getMovieState(movie.movieId);
    setState(next);
    setFeedback(active ? (type === "watchlisted" ? "Added to Watchlist" : type === "liked" ? "Marked as liked" : "Noted: less like this") : "Removed");
    window.setTimeout(() => setFeedback(""), 1400);
  };

  const rememberContext = () => {
    try {
      window.sessionStorage.setItem("moviemate_last_movie_context", JSON.stringify(movie));
    } catch {
      // Ignore storage failures; navigation should still work.
    }
  };

  const genres = movie.genres?.split(",").map((g) => g.trim()).filter(Boolean).slice(0, 2) ?? [];
  const title = sanitizeTitle(movie.title) || "Untitled";
  const ratingText =
    typeof movie.rating_avg === "number" && typeof movie.rating_count === "number"
      ? `Avg ${movie.rating_avg.toFixed(2)} / ${movie.rating_count} ratings`
      : "";
  const highlight = movie.highlight || movie.review_snippet || (movie.overview ? movie.overview.split(/(?<=[.!?])\s+/)[0] : "");
  const highlightLabel = movie.review_snippet ? "Movie Highlight" : "Story Highlight";

  return (
    <motion.article
      whileHover={{ scale: 1.045, y: -5 }}
      transition={{ type: "spring", stiffness: 170, damping: 22 }}
      className="group relative min-w-[180px] max-w-[180px] overflow-hidden rounded-2xl border border-white/10 bg-panel shadow-glow transition-colors duration-300 hover:border-neon/35 md:min-w-[220px] md:max-w-[220px]"
    >
      <div className="relative">
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
        <span className="absolute left-2 top-2 rounded-full border border-black/30 bg-black/70 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-cyan-100 backdrop-blur">
          {reasonTypeLabel(movie.reason_type)}
        </span>
      </div>

      <div className="space-y-2 p-3">
        <div>
          <p className="line-clamp-1 text-sm font-semibold text-white">{title}</p>
          <p className="text-[11px] text-slate-500">{movie.year || "Unknown year"}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {genres.map((g) => (
            <GenreBadge key={g} text={g} />
          ))}
          <RatingBadge score={movie.score} />
        </div>
        {ratingText && <p className="line-clamp-1 text-[11px] text-slate-400">{ratingText}</p>}
        <ReasonTooltip movie={movie} />
      </div>

      <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/95 via-black/50 to-transparent p-3 opacity-0 transition duration-300 group-hover:opacity-100">
        <p className="mb-2 line-clamp-4 text-xs leading-5 text-slate-200">{movie.overview || "No overview available."}</p>
        {highlight && (
          <div className="mb-3 rounded-xl border border-neon/20 bg-neon/10 p-2">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neon">{highlightLabel}</p>
            <p className="mt-1 line-clamp-2 text-xs text-cyan-50">{highlight}</p>
          </div>
        )}
        {feedback && <p className="mb-2 rounded-full bg-white/15 px-3 py-1 text-center text-[11px] text-white">{feedback}</p>}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link to={`/movie/${movie.movieId}`} onClick={rememberContext} className="rounded-full bg-neon/20 px-3 py-1 font-semibold text-neon transition hover:bg-neon hover:text-ink">
            View Detail
          </Link>
          <Link to={`/similar?movieId=${movie.movieId}`} onClick={rememberContext} className="rounded-full bg-coral/20 px-3 py-1 font-semibold text-coral transition hover:bg-coral hover:text-white">
            Similar
          </Link>
          <ActionButton active={state.liked} label="Like" activeLabel="Liked" onClick={() => updateAction("liked")}>
            {state.liked ? <Check size={12} /> : <Heart size={12} />}
          </ActionButton>
          <ActionButton active={state.disliked} label="Not for me" activeLabel="Hidden" onClick={() => updateAction("disliked")}>
            <ThumbsDown size={12} />
          </ActionButton>
          <ActionButton active={state.watchlisted} label="Watchlist" activeLabel="Saved" onClick={() => updateAction("watchlisted")}>
            <BookmarkPlus size={12} />
          </ActionButton>
        </div>
      </div>
    </motion.article>
  );
}
