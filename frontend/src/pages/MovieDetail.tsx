import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchMovieDetail } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";
import { PLACEHOLDER_POSTER, sanitizeBackdropUrl, sanitizePosterUrl, sanitizeTitle } from "../utils/movie";

export function MovieDetail() {
  const { movieId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [movie, setMovie] = useState<any>(null);

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
      setLoading(true);
      setError("");
      try {
        setMovie(await fetchMovieDetail(Number(movieId)));
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
              {movie.year || "Unknown Year"} / {movie.genres || "Unknown Genre"} / {movie.runtime ? `${Math.round(movie.runtime)} min` : "Runtime unknown"}
            </p>
            <p className="line-clamp-4 text-sm leading-6 text-slate-200 md:text-base">{movie.overview || "No overview available."}</p>
            <div className="flex flex-wrap gap-2 text-xs text-slate-300">
              <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">Cast: {movie.cast || "Not available"}</span>
              <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">Director: {movie.director || "Not available"}</span>
              <span className="rounded-full border border-amber-300/25 bg-amber-300/10 px-3 py-1 text-amber-100">MovieLens {ratingAvg} from {ratingCount} ratings</span>
            </div>
          </div>
        </div>
      </div>

      <section className="space-y-4 rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.28em] text-slate-500">Audience Signals</p>
            <h2 className="mt-2 text-2xl font-black text-white">Reviews & Ratings</h2>
            <p className="text-sm text-slate-400">MovieLens average {ratingAvg} from {ratingCount} ratings</p>
          </div>
          {typeof movie.vote_average === "number" && <p className="text-sm text-slate-300">TMDB average {movie.vote_average.toFixed(2)}</p>}
        </div>
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

      <MovieRow title="Similar Movies" movies={movie.similar_movies || []} />
    </section>
  );
}
