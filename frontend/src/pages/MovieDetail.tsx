import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchMovieDetail, fetchSimilarMovies } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";
import { MovieCard } from "../types";
import { PLACEHOLDER_POSTER, sanitizeBackdropUrl, sanitizePosterUrl, sanitizeTitle } from "../utils/movie";

function getLastContext(movieId: number): Partial<MovieCard> | null {
  try {
    const raw = window.sessionStorage.getItem("moviemate_last_movie_context");
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed && Number(parsed.movieId) === Number(movieId) ? parsed : null;
  } catch {
    return null;
  }
}

function overlapGenres(movie: MovieCard) {
  const own = (movie.genres || "").split(",").map((x) => x.trim()).filter(Boolean);
  const source = (movie.source_movie?.genres || "").split(",").map((x) => x.trim()).filter(Boolean);
  const sourceSet = new Set(source.map((x) => x.toLowerCase()));
  const overlap = own.filter((genre) => sourceSet.has(genre.toLowerCase()));
  return overlap.length ? overlap : own.slice(0, 4);
}

function scoreRows(movie: MovieCard) {
  const breakdown = movie.score_breakdown || {};
  const fallback = typeof movie.score === "number" ? movie.score : Number(movie.rating_avg || 0);
  return [
    { label: "MF / SVD", value: breakdown.mf ?? breakdown.recommendation ?? fallback, hint: "Latent preference prediction" },
    { label: "ItemCF", value: breakdown.itemcf ?? breakdown.rating_avg ?? fallback, hint: "Similar-movie signal" },
    { label: "Content", value: breakdown.content ?? breakdown.popularity ?? fallback, hint: "Genre, tag, and story match" },
    { label: "Popularity", value: breakdown.popularity ?? breakdown.rating_count ?? fallback, hint: "Crowd rating and volume" }
  ];
}

export function MovieDetail() {
  const { movieId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [movie, setMovie] = useState<MovieCard | null>(null);
  const [contentSimilar, setContentSimilar] = useState<MovieCard[]>([]);
  const [collaborativeSimilar, setCollaborativeSimilar] = useState<MovieCard[]>([]);

  const safePoster = useMemo(() => sanitizePosterUrl(movie?.poster_url), [movie?.poster_url]);
  const safeBackdrop = useMemo(() => sanitizeBackdropUrl(movie?.backdrop_url), [movie?.backdrop_url]);
  const title = useMemo(() => sanitizeTitle(movie?.title) || "Untitled", [movie?.title]);

  const [bannerSrc, setBannerSrc] = useState<string>("");
  const [bannerFailed, setBannerFailed] = useState(false);
  const [posterSrc, setPosterSrc] = useState<string>(PLACEHOLDER_POSTER);
  const [posterFailed, setPosterFailed] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!movieId) return;
      const numericId = Number(movieId);
      setLoading(true);
      setError("");
      try {
        const [detail, content, itemcf] = await Promise.all([
          fetchMovieDetail(numericId),
          fetchSimilarMovies(numericId, "content", 12).catch(() => []),
          fetchSimilarMovies(numericId, "itemcf", 12).catch(() => [])
        ]);
        const context = getLastContext(numericId);
        setMovie({ ...detail, ...context, movieId: numericId } as MovieCard);
        setContentSimilar(content);
        setCollaborativeSimilar(itemcf.length ? itemcf : detail.similar_movies || []);
      } catch {
        setError("Failed to load movie detail.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [movieId]);

  useEffect(() => {
    setBannerSrc(safeBackdrop || safePoster || "");
    setBannerFailed(false);
    setPosterSrc(safePoster || PLACEHOLDER_POSTER);
    setPosterFailed(false);
  }, [movie?.movieId, safeBackdrop, safePoster]);

  if (loading) return <LoadingSkeleton className="h-96" />;
  if (error) return <p className="rounded-2xl border border-coral/30 bg-coral/15 p-4 text-coral">{error}</p>;
  if (!movie) return null;

  const ratingAvg = typeof movie.rating_avg === "number" ? movie.rating_avg.toFixed(2) : "-";
  const ratingCount = typeof movie.rating_count === "number" ? movie.rating_count : 0;
  const reviews = Array.isArray(movie.reviews) ? movie.reviews.slice(0, 8) : [];
  const matchedGenres = overlapGenres(movie);
  const predictedScore = typeof movie.score === "number" ? movie.score.toFixed(3) : movie.score_breakdown?.recommendation != null ? Number(movie.score_breakdown.recommendation).toFixed(3) : "N/A";

  return (
    <section className="space-y-8">
      <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-panel shadow-glow">
        {bannerSrc ? (
          <img
            src={bannerSrc}
            alt={title}
            className={`h-[360px] w-full object-cover md:h-[500px] ${!safeBackdrop ? "scale-110 blur-sm" : ""}`}
            onError={() => {
              if (bannerFailed) return;
              setBannerFailed(true);
              if (bannerSrc !== safePoster && safePoster && safePoster !== PLACEHOLDER_POSTER) {
                setBannerSrc(safePoster);
                return;
              }
              setBannerSrc("");
            }}
          />
        ) : (
          <div className="h-[360px] w-full bg-gradient-to-r from-slate-950 via-slate-900 to-black md:h-[500px]" />
        )}
        <div className="absolute inset-0 bg-gradient-to-r from-black/90 via-black/55 to-transparent" />
        <div className="absolute bottom-0 left-0 flex w-full gap-5 p-5 md:p-8">
          <img
            src={posterSrc}
            alt={title}
            className="hidden h-56 w-36 rounded-2xl border border-white/10 object-cover shadow-2xl md:block"
            onError={() => {
              if (posterFailed) return;
              setPosterFailed(true);
              setPosterSrc(PLACEHOLDER_POSTER);
            }}
          />
          <div className="max-w-3xl space-y-3">
            <p className="w-fit rounded-full border border-neon/30 bg-neon/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.24em] text-neon">Movie Detail</p>
            <h1 className="text-3xl font-black leading-tight md:text-6xl">{title}</h1>
            <p className="text-sm text-slate-200">
              {movie.year || "Unknown Year"} / {movie.genres || "Unknown Genre"} / {(movie as any).runtime ? `${Math.round((movie as any).runtime)} min` : "Runtime unknown"}
            </p>
            <p className="line-clamp-4 text-sm leading-6 text-slate-200 md:text-base">{movie.overview || "No overview available."}</p>
            <div className="flex flex-wrap gap-2 text-xs text-slate-300">
              <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">Cast: {(movie as any).cast || "Not available"}</span>
              <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">Director: {(movie as any).director || "Not available"}</span>
              <span className="rounded-full border border-amber-300/25 bg-amber-300/10 px-3 py-1 text-amber-100">MovieLens {ratingAvg} from {ratingCount} ratings</span>
            </div>
          </div>
        </div>
      </div>

      <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-[1.6rem] border border-neon/25 bg-neon/10 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-neon">Why this movie?</p>
          <h2 className="mt-2 text-2xl font-black text-white">Recommendation Explanation</h2>
          <div className="mt-4 space-y-4 text-sm text-cyan-50">
            <p><span className="text-slate-400">Predicted score:</span> {predictedScore}</p>
            <p><span className="text-slate-400">Reason:</span> {movie.reason || "This title balances collaborative, content, and popularity signals."}</p>
            <p><span className="text-slate-400">Evidence:</span> {movie.evidence || "Matched from the current recommendation shelf or movie similarity cache."}</p>
            <div>
              <p className="text-slate-400">Matched genres</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {matchedGenres.map((genre) => (
                  <span key={genre} className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-white">{genre}</span>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-slate-500">Score Breakdown</p>
          <h2 className="mt-2 text-2xl font-black text-white">Model signal composition</h2>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {scoreRows(movie).map((row) => (
              <div key={row.label} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-bold text-white">{row.label}</p>
                  <p className="text-lg font-black text-neon">{typeof row.value === "number" ? row.value.toFixed(row.value > 10 ? 0 : 3) : "N/A"}</p>
                </div>
                <p className="mt-2 text-xs text-slate-400">{row.hint}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="space-y-4 rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.28em] text-slate-500">Audience Signals</p>
            <h2 className="mt-2 text-2xl font-black text-white">Reviews & Ratings</h2>
            <p className="text-sm text-slate-400">MovieLens average {ratingAvg} from {ratingCount} ratings</p>
          </div>
          {typeof (movie as any).vote_average === "number" && <p className="text-sm text-slate-300">TMDB average {(movie as any).vote_average.toFixed(2)}</p>}
        </div>
        {movie.highlight && (
          <div className="rounded-2xl border border-neon/20 bg-neon/10 p-4 text-sm text-cyan-50">
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-neon">Movie Highlight</p>
            <p className="mt-2">{movie.highlight}</p>
          </div>
        )}
        {reviews.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {reviews.map((review: { text: string; rating?: number | null; userId?: number | null }, index: number) => (
              <blockquote key={`${review.text}-${index}`} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm leading-6 text-slate-200">
                {review.text}
                {review.rating != null && <span className="mt-2 block text-xs text-amber-200">Rating {review.rating}</span>}
              </blockquote>
            ))}
          </div>
        ) : (
          <p className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm text-slate-400">
            No short review tags are available yet, but this movie still participates in rating prediction and similar-movie ranking.
          </p>
        )}
      </section>

      <MovieRow title="Content Similar" movies={contentSimilar} />
      <MovieRow title="Collaborative Similar" movies={collaborativeSimilar} />
    </section>
  );
}
