import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchMovieDetail } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";

export function MovieDetail() {
  const { movieId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [movie, setMovie] = useState<any>(null);

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

  if (loading) return <LoadingSkeleton className="h-96" />;
  if (error) return <p className="rounded-md bg-coral/20 p-3 text-coral">{error}</p>;
  if (!movie) return null;

  const backdropFallback = movie.poster_url || "/placeholder-poster.png";
  const posterFallback = "/placeholder-poster.png";

  return (
    <section className="space-y-6">
      <div className="relative overflow-hidden rounded-2xl border border-white/10">
        {movie.backdrop_url || movie.poster_url ? (
          <img
            src={movie.backdrop_url || movie.poster_url || posterFallback}
            alt={movie.title}
            className={`h-[320px] w-full object-cover md:h-[420px] ${!movie.backdrop_url ? "scale-110 blur-sm" : ""}`}
            onError={(e) => {
              e.currentTarget.src = backdropFallback;
            }}
          />
        ) : (
          <div className="h-[320px] w-full bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 md:h-[420px]" />
        )}
        <div className="absolute inset-0 bg-gradient-to-r from-black/85 to-transparent" />
        <div className="absolute bottom-0 left-0 flex gap-4 p-4 md:p-8">
          <img
            src={movie.poster_url || posterFallback}
            alt={movie.title}
            className="hidden h-48 w-32 rounded-md object-cover md:block"
            onError={(e) => {
              e.currentTarget.src = posterFallback;
            }}
          />
          <div className="max-w-2xl space-y-2">
            <h1 className="text-3xl font-bold md:text-5xl">{movie.title}</h1>
            <p className="text-sm text-slate-200">{movie.year} • {movie.genres} • {movie.runtime ? `${Math.round(movie.runtime)} min` : "-"}</p>
            <p className="text-sm text-slate-200">{movie.overview}</p>
            <p className="text-sm text-slate-200">Cast: {movie.cast || "-"}</p>
            <p className="text-sm text-slate-200">Director: {movie.director || "-"}</p>
            <p className="text-sm text-gold">Average Rating: {movie.vote_average?.toFixed?.(2) ?? "-"}</p>
          </div>
        </div>
      </div>
      <MovieRow title="Similar Movies" movies={movie.similar_movies || []} />
    </section>
  );
}

