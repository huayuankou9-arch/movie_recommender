import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchSearch, fetchSimilarMovies } from "../api/client";
import { MovieCard } from "../components/MovieCard";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieCard as Movie } from "../types";

export function SimilarMovies() {
  const [params] = useSearchParams();
  const initial = Number(params.get("movieId") || 1);
  const [movieId, setMovieId] = useState(initial);
  const [titleQuery, setTitleQuery] = useState("");
  const [method, setMethod] = useState("hybrid");
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setMovies(await fetchSimilarMovies(movieId, method, 18));
    } catch (e) {
      setError("Failed to load similar movies.");
    } finally {
      setLoading(false);
    }
  };

  const searchAndFill = async () => {
    if (!titleQuery.trim()) return;
    setLoading(true);
    setError("");
    try {
      const items = await fetchSearch(titleQuery, 1);
      if (!items.length) {
        setError("No movie matched this title.");
        return;
      }
      setMovieId(items[0].movieId);
    } catch (e) {
      setError("Failed to search movie title.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <section className="space-y-5">
      <h1 className="text-2xl font-bold md:text-3xl">Similar Movies</h1>
      <div className="flex flex-wrap gap-3 rounded-xl border border-white/10 bg-panel p-4">
        <input type="number" value={movieId} onChange={(e) => setMovieId(Number(e.target.value || 1))} className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm" />
        <input
          value={titleQuery}
          onChange={(e) => setTitleQuery(e.target.value)}
          placeholder="or search by title"
          className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm"
        />
        <button onClick={searchAndFill} className="rounded-md border border-neon/40 px-3 py-2 text-xs text-neon">
          Find Id
        </button>
        <select value={method} onChange={(e) => setMethod(e.target.value)} className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm">
          <option value="itemcf">ItemCF</option>
          <option value="content">Content-based</option>
          <option value="hybrid">Hybrid</option>
          <option value="mf">MF</option>
        </select>
        <button onClick={load} className="rounded-md bg-neon px-4 py-2 text-sm font-semibold text-ink">
          Find Similar
        </button>
      </div>
      {loading && <LoadingSkeleton className="h-48" />}
      {error && <p className="rounded-md bg-coral/20 px-3 py-2 text-coral">{error}</p>}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
        {movies.map((m) => (
          <MovieCard key={m.movieId} movie={m} />
        ))}
      </div>
    </section>
  );
}
