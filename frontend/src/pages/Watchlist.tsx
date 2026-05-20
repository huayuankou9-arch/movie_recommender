import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchSimilarMovies } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieCard } from "../components/MovieCard";
import { MovieRow } from "../components/MovieRow";
import { MovieCard as Movie } from "../types";
import { getLibraryMovies, onLibraryChange, removeMovie } from "../utils/library";
import { PLACEHOLDER_POSTER, sanitizePosterUrl, sanitizeTitle } from "../utils/movie";

function WatchlistItem({ movie, onRemove }: { movie: Movie; onRemove: () => void }) {
  const title = sanitizeTitle(movie.title) || "Untitled";
  return (
    <div className="flex gap-4 rounded-2xl border border-white/10 bg-white/[0.04] p-3">
      <img
        src={sanitizePosterUrl(movie.poster_url) || PLACEHOLDER_POSTER}
        alt={title}
        className="h-32 w-24 rounded-xl object-cover"
        onError={(e) => {
          e.currentTarget.src = PLACEHOLDER_POSTER;
        }}
      />
      <div className="min-w-0 flex-1">
        <h3 className="line-clamp-1 font-black text-white">{title}</h3>
        <p className="mt-1 text-xs text-slate-400">{movie.year || "Unknown year"} / {movie.genres || "Unknown genre"}</p>
        <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-300">{movie.overview || movie.reason || "Saved to watch later."}</p>
        <button onClick={onRemove} className="mt-3 inline-flex items-center gap-2 rounded-full border border-coral/30 bg-coral/10 px-3 py-1.5 text-xs font-semibold text-coral transition hover:bg-coral hover:text-white">
          <Trash2 size={13} />
          Remove
        </button>
      </div>
    </div>
  );
}

export function Watchlist() {
  const [movies, setMovies] = useState<Movie[]>(() => getLibraryMovies("watchlist"));
  const [recommendations, setRecommendations] = useState<Movie[]>([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);

  const refresh = () => setMovies(getLibraryMovies("watchlist"));

  useEffect(() => onLibraryChange(refresh), []);

  useEffect(() => {
    const loadSimilar = async () => {
      if (!movies.length) {
        setRecommendations([]);
        return;
      }
      setLoadingSimilar(true);
      try {
        const batches = await Promise.all(movies.slice(0, 3).map((movie) => fetchSimilarMovies(movie.movieId, "hybrid", 8).catch(() => [])));
        const seen = new Set(movies.map((movie) => movie.movieId));
        const merged: Movie[] = [];
        for (const batch of batches.flat()) {
          if (seen.has(batch.movieId)) continue;
          seen.add(batch.movieId);
          merged.push({ ...batch, reason: batch.reason || "Recommended from your watchlist", reason_type: batch.reason_type || "hybrid" });
          if (merged.length >= 18) break;
        }
        setRecommendations(merged);
      } finally {
        setLoadingSimilar(false);
      }
    };
    loadSimilar();
  }, [movies]);

  const remove = (movieId: number) => {
    removeMovie("watchlist", movieId);
    refresh();
  };

  return (
    <section className="space-y-8">
      <div className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(0,224,255,0.18),transparent_32%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,0.82))] p-6 md:p-8">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-neon">Personal Library</p>
        <h1 className="mt-3 text-3xl font-black tracking-tight md:text-5xl">Watchlist</h1>
        <p className="mt-4 max-w-3xl text-base leading-7 text-slate-300">
          Your saved movies live locally in this browser. MovieMate can also use them as seed items to generate similar recommendations.
        </p>
      </div>

      {movies.length === 0 ? (
        <div className="rounded-[1.6rem] border border-dashed border-white/15 bg-white/[0.03] p-8 text-center text-slate-400">
          Your watchlist is empty. Hover any movie card and click Watchlist to save it here.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {movies.map((movie) => (
            <WatchlistItem key={movie.movieId} movie={movie} onRemove={() => remove(movie.movieId)} />
          ))}
        </div>
      )}

      {loadingSimilar && <LoadingSkeleton className="h-48" />}
      {!loadingSimilar && recommendations.length > 0 && <MovieRow title="Because of your Watchlist" movies={recommendations} />}

      {movies.length > 0 && recommendations.length === 0 && !loadingSimilar && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
          {movies.map((movie) => (
            <MovieCard key={`saved-card-${movie.movieId}`} movie={movie} />
          ))}
        </div>
      )}
    </section>
  );
}
