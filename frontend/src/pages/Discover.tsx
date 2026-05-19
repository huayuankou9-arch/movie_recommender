import { useState } from "react";
import { fetchDiscover } from "../api/client";
import { MovieCard } from "../components/MovieCard";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieCard as Movie } from "../types";

export function Discover() {
  const [genres, setGenres] = useState("Action,Drama");
  const [keywords, setKeywords] = useState("space,love");
  const [yearMin, setYearMin] = useState(2000);
  const [yearMax, setYearMax] = useState(2020);
  const [style, setStyle] = useState("popular");
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      let yMin = yearMin;
      let yMax = yearMax;
      if (style === "classic") {
        yMax = 2005;
      }
      const items = await fetchDiscover({
        genres,
        keywords,
        year_min: yMin,
        year_max: yMax,
        top_k: 24
      });
      setMovies(items);
    } catch (e) {
      setError("Discover failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-5">
      <h1 className="text-2xl font-bold md:text-3xl">Discover</h1>
      <div className="grid grid-cols-1 gap-3 rounded-xl border border-white/10 bg-panel/80 p-4 md:grid-cols-6">
        <input value={genres} onChange={(e) => setGenres(e.target.value)} className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm md:col-span-2" placeholder="genres: Action,Drama" />
        <input value={keywords} onChange={(e) => setKeywords(e.target.value)} className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm md:col-span-2" placeholder="keywords: space,love" />
        <input type="number" value={yearMin} onChange={(e) => setYearMin(Number(e.target.value))} className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm" />
        <input type="number" value={yearMax} onChange={(e) => setYearMax(Number(e.target.value))} className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm" />
        <select value={style} onChange={(e) => setStyle(e.target.value)} className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm">
          <option value="popular">Popular</option>
          <option value="highly_rated">Highly Rated</option>
          <option value="niche">Niche</option>
          <option value="classic">Classic</option>
        </select>
        <button onClick={run} className="rounded-md bg-neon px-4 py-2 text-sm font-semibold text-ink">
          Recommend
        </button>
      </div>
      {loading && <LoadingSkeleton className="h-44 w-full" />}
      {error && <p className="rounded-md bg-coral/20 px-3 py-2 text-coral">{error}</p>}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
        {movies.map((m) => (
          <MovieCard key={m.movieId} movie={m} />
        ))}
      </div>
    </section>
  );
}
