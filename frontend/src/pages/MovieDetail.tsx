import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchMovieDetail, repairPoster } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";

export function MovieDetail() {
  const { movieId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [movie, setMovie] = useState<any>(null);
  const backdropRepairTried = useRef(false);
  const posterRepairTried = useRef(false);

  useEffect(() => {
    const load = async () => {
      if (!movieId) return;
      setLoading(true);
      setError("");
      try {
        setMovie(await fetchMovieDetail(Number(movieId)));
      } catch (e) {
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
  const backdropFallback = "https://placehold.co/1200x675?text=No+Backdrop";
  const posterFallback = "https://placehold.co/500x750?text=No+Poster";

  return (
    <section className="space-y-6">
      <div className="relative overflow-hidden rounded-2xl border border-white/10">
        <img
          src={movie.backdrop_url || backdropFallback}
          alt={movie.title}
          className="h-[320px] w-full object-cover md:h-[420px]"
          onError={async (e) => {
            const t = e.currentTarget;
            if (backdropRepairTried.current) {
              if (t.src !== backdropFallback) t.src = backdropFallback;
              return;
            }
            backdropRepairTried.current = true;
            try {
              const fixed = await repairPoster(Number(movie.movieId), t.src);
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
            t.src = backdropFallback;
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black/85 to-transparent" />
        <div className="absolute bottom-0 left-0 flex gap-4 p-4 md:p-8">
          <img
            src={movie.poster_url || posterFallback}
            alt={movie.title}
            className="hidden h-48 w-32 rounded-md object-cover md:block"
            onError={async (e) => {
              const t = e.currentTarget;
              if (posterRepairTried.current) {
                if (t.src !== posterFallback) t.src = posterFallback;
                return;
              }
              posterRepairTried.current = true;
              try {
                const fixed = await repairPoster(Number(movie.movieId), t.src);
                if (fixed.poster_url && fixed.poster_url !== t.src) {
                  t.src = fixed.poster_url;
                  return;
                }
              } catch (_err) {
                // fall back below
              }
              t.src = posterFallback;
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
