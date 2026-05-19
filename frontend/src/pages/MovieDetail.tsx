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
      } catch (_e) {
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
  if (error) return <p className="rounded-md bg-coral/20 p-3 text-coral">{error}</p>;
  if (!movie) return null;

  const ratingAvg = typeof movie.rating_avg === "number" ? movie.rating_avg.toFixed(2) : "-";
  const ratingCount = typeof movie.rating_count === "number" ? movie.rating_count : 0;
  const reviews = Array.isArray(movie.reviews) ? movie.reviews.slice(0, 8) : [];

  return (
    <section className="space-y-6">
      <div className="relative overflow-hidden rounded-2xl border border-white/10">
        {bannerSrc ? (
          <img
            src={bannerSrc}
            alt={title}
            className={`h-[320px] w-full object-cover md:h-[420px] ${!safeBackdrop ? "scale-110 blur-sm" : ""}`}
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
          <div className="h-[320px] w-full bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 md:h-[420px]" />
        )}
        <div className="absolute inset-0 bg-gradient-to-r from-black/85 to-transparent" />
        <div className="absolute bottom-0 left-0 flex gap-4 p-4 md:p-8">
          <img
            src={posterSrc}
            alt={title}
            className="hidden h-48 w-32 rounded-md object-cover md:block"
            onError={() => {
              if (posterFailed) return;
              setPosterFailed(true);
              setPosterSrc(PLACEHOLDER_POSTER);
            }}
          />
          <div className="max-w-2xl space-y-2">
            <h1 className="text-3xl font-bold md:text-5xl">{title}</h1>
            <p className="text-sm text-slate-200">
              {movie.year || "Unknown Year"} - {movie.genres || "Unknown Genre"} -{" "}
              {movie.runtime ? `${Math.round(movie.runtime)} min` : "-"}
            </p>
            <p className="text-sm text-slate-200">{movie.overview || "No overview available."}</p>
            <p className="text-sm text-slate-200">Cast: {movie.cast || "-"}</p>
            <p className="text-sm text-slate-200">Director: {movie.director || "-"}</p>
            <p className="text-sm text-gold">
              MovieLens Rating: {ratingAvg} ({ratingCount} ratings)
            </p>
          </div>
        </div>
      </div>
      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-white">Reviews & Ratings</h2>
            <p className="text-sm text-slate-400">
              MovieLens average {ratingAvg} from {ratingCount} ratings
            </p>
          </div>
          {typeof movie.vote_average === "number" && (
            <p className="text-sm text-slate-300">TMDB average {movie.vote_average.toFixed(2)}</p>
          )}
        </div>
        {reviews.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {reviews.map((review: { text: string }, index: number) => (
              <blockquote key={`${review.text}-${index}`} className="rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-200">
                {review.text}
              </blockquote>
            ))}
          </div>
        ) : (
          <p className="rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-400">
            暂无用户标签短评，但该电影仍参与评分与相似推荐计算。
          </p>
        )}
      </section>
      <MovieRow title="Similar Movies" movies={movie.similar_movies || []} />
    </section>
  );
}
