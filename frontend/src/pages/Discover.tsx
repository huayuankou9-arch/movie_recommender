import { useState } from "react";
import { fetchDiscover } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieCard } from "../components/MovieCard";
import { MovieCard as Movie } from "../types";

const GENRE_OPTIONS = ["Action", "Adventure", "Animation", "Comedy", "Crime", "Drama", "Fantasy", "Romance", "Sci-Fi", "Thriller"];
const STYLE_COPY: Record<string, string> = {
  popular: "Prioritize broadly loved, high-confidence movies.",
  highly_rated: "Lean into quality and stronger rating signals.",
  niche: "Surface slightly more specific picks from your selected taste space.",
  classic: "Favor older titles that still travel well."
};

export function Discover() {
  const [selectedGenres, setSelectedGenres] = useState<string[]>(["Action", "Drama"]);
  const [keywords, setKeywords] = useState("space, love");
  const [yearMin, setYearMin] = useState(2000);
  const [yearMax, setYearMax] = useState(2020);
  const [style, setStyle] = useState("popular");
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const toggleGenre = (genre: string) => {
    setSelectedGenres((prev) => (prev.includes(genre) ? prev.filter((g) => g !== genre) : [...prev, genre]));
  };

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      let yMin = yearMin;
      let yMax = yearMax;
      if (style === "classic") {
        yMin = 1900;
        yMax = Math.min(yearMax, 2005);
      }
      const items = await fetchDiscover({
        genres: selectedGenres.join(","),
        keywords,
        year_min: yMin,
        year_max: yMax,
        top_k: style === "niche" ? 30 : 24
      });
      const styled = style === "highly_rated" ? [...items].sort((a, b) => Number(b.rating_avg || 0) - Number(a.rating_avg || 0)) : items;
      setMovies(styled.slice(0, 24));
    } catch {
      setError("Discovery failed. Try broadening your genres or year range.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-8">
      <div className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_20%_0%,rgba(255,202,86,0.22),transparent_30%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,0.82))] p-6 md:p-8">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-amber-300">Cold Start Discovery</p>
        <h1 className="mt-3 text-3xl font-black tracking-tight md:text-5xl">Tell us what you like.</h1>
        <p className="mt-4 max-w-3xl text-base leading-7 text-slate-300">
          No viewing history? No problem. Pick a few signals and MovieMate builds a lightweight starter profile from genres, era, style, and keywords.
        </p>
      </div>

      <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-5">
            <div>
              <p className="mb-3 text-sm font-semibold text-white">Genres</p>
              <div className="flex flex-wrap gap-2">
                {GENRE_OPTIONS.map((genre) => {
                  const active = selectedGenres.includes(genre);
                  return (
                    <button
                      key={genre}
                      onClick={() => toggleGenre(genre)}
                      className={`rounded-full border px-4 py-2 text-sm transition ${
                        active ? "border-neon bg-neon text-ink" : "border-white/10 bg-white/5 text-slate-300 hover:border-white/30 hover:bg-white/10"
                      }`}
                    >
                      {genre}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <label className="text-sm text-slate-300 md:col-span-2">
                Keywords
                <input
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                  className="mt-2 w-full rounded-2xl border border-white/15 bg-black/25 px-4 py-3 text-sm outline-none focus:border-neon"
                  placeholder="space, love, revenge"
                />
              </label>
              <label className="text-sm text-slate-300">
                From
                <input type="number" value={yearMin} onChange={(e) => setYearMin(Number(e.target.value))} className="mt-2 w-full rounded-2xl border border-white/15 bg-black/25 px-4 py-3 text-sm outline-none focus:border-neon" />
              </label>
              <label className="text-sm text-slate-300">
                To
                <input type="number" value={yearMax} onChange={(e) => setYearMax(Number(e.target.value))} className="mt-2 w-full rounded-2xl border border-white/15 bg-black/25 px-4 py-3 text-sm outline-none focus:border-neon" />
              </label>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-black/25 p-4">
            <p className="text-sm font-semibold text-white">Recommendation Style</p>
            <div className="mt-3 space-y-2">
              {Object.keys(STYLE_COPY).map((key) => (
                <button
                  key={key}
                  onClick={() => setStyle(key)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                    style === key ? "border-coral bg-coral/20 text-white" : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                  }`}
                >
                  <span className="block text-sm font-bold capitalize">{key.replace("_", " ")}</span>
                  <span className="mt-1 block text-xs text-slate-400">{STYLE_COPY[key]}</span>
                </button>
              ))}
            </div>
            <button onClick={run} className="mt-4 w-full rounded-full bg-neon px-5 py-3 text-sm font-bold text-ink transition hover:bg-white">
              Build My Starter Shelf
            </button>
          </div>
        </div>
      </div>

      {loading && <LoadingSkeleton className="h-48 w-full" />}
      {error && <p className="rounded-2xl border border-coral/30 bg-coral/15 px-4 py-3 text-coral">{error}</p>}

      <div className="space-y-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-slate-500">Cold-start output</p>
          <h2 className="mt-2 text-2xl font-black">Movies for your new profile</h2>
        </div>
        {movies.length === 0 && !loading ? (
          <div className="rounded-[1.6rem] border border-dashed border-white/15 bg-white/[0.03] p-8 text-center text-slate-400">
            Choose your taste signals and build a starter shelf.
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
            {movies.map((m) => (
              <MovieCard key={m.movieId} movie={m} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
