import { useState } from "react";
import { fetchDiscover } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieCard } from "../components/MovieCard";
import { MovieCard as Movie } from "../types";

const GENRE_OPTIONS = ["Action", "Adventure", "Animation", "Comedy", "Crime", "Drama", "Fantasy", "Romance", "Sci-Fi", "Thriller", "Children"];
const STYLE_OPTIONS = [
  { key: "light", label: "Light-hearted", keywords: "fun, friendship, comedy, feel good", hint: "Relaxed, warm, easy to watch." },
  { key: "thought", label: "Thought-provoking", keywords: "mind, identity, dystopia, moral", hint: "Ideas, tension, and after-movie discussion." },
  { key: "classic", label: "Classic", keywords: "classic, acclaimed, timeless", hint: "Older or enduring favorites." },
  { key: "niche", label: "Niche", keywords: "independent, unusual, cult", hint: "Less obvious picks with stronger personality." },
  { key: "family", label: "Family-friendly", keywords: "family, adventure, animation", hint: "Safe, broad, and accessible." },
  { key: "blockbuster", label: "Blockbuster", keywords: "action, spectacle, hero, adventure", hint: "Big, energetic, crowd-pleasing films." }
];

export function Discover() {
  const [selectedGenres, setSelectedGenres] = useState<string[]>(["Action", "Drama"]);
  const [style, setStyle] = useState("thought");
  const [yearMin, setYearMin] = useState(2000);
  const [yearMax, setYearMax] = useState(2020);
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
      const selectedStyle = STYLE_OPTIONS.find((item) => item.key === style) || STYLE_OPTIONS[0];
      let genres = selectedGenres;
      let yMin = yearMin;
      let yMax = yearMax;
      if (style === "classic") {
        yMin = 1900;
        yMax = Math.min(yearMax, 2005);
      }
      if (style === "family") {
        genres = Array.from(new Set([...selectedGenres, "Animation", "Children", "Adventure"]));
      }
      if (style === "blockbuster") {
        genres = Array.from(new Set([...selectedGenres, "Action", "Adventure"]));
      }
      const items = await fetchDiscover({
        genres: genres.join(","),
        keywords: selectedStyle.keywords,
        year_min: yMin,
        year_max: yMax,
        top_k: style === "niche" ? 30 : 24
      });
      const ranked = style === "niche" ? items.slice().reverse() : items;
      setMovies(ranked.slice(0, 24));
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
          A three-step onboarding flow for new users: choose genres, choose a viewing mood, then choose the era you want to explore.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <section className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.25em] text-neon">Step 1</p>
          <h2 className="mt-2 text-xl font-black">Pick favorite genres</h2>
          <div className="mt-4 flex flex-wrap gap-2">
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
        </section>

        <section className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.25em] text-coral">Step 2</p>
          <h2 className="mt-2 text-xl font-black">Choose the vibe</h2>
          <div className="mt-4 space-y-2">
            {STYLE_OPTIONS.map((item) => (
              <button
                key={item.key}
                onClick={() => setStyle(item.key)}
                className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                  style === item.key ? "border-coral bg-coral/20 text-white" : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                }`}
              >
                <span className="block text-sm font-bold">{item.label}</span>
                <span className="mt-1 block text-xs text-slate-400">{item.hint}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.25em] text-amber-300">Step 3</p>
          <h2 className="mt-2 text-xl font-black">Select an era</h2>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <label className="text-sm text-slate-300">
              From
              <input type="number" value={yearMin} onChange={(e) => setYearMin(Number(e.target.value))} className="mt-2 w-full rounded-2xl border border-white/15 bg-black/25 px-4 py-3 text-sm outline-none focus:border-neon" />
            </label>
            <label className="text-sm text-slate-300">
              To
              <input type="number" value={yearMax} onChange={(e) => setYearMax(Number(e.target.value))} className="mt-2 w-full rounded-2xl border border-white/15 bg-black/25 px-4 py-3 text-sm outline-none focus:border-neon" />
            </label>
          </div>
          <div className="mt-5 rounded-2xl border border-white/10 bg-black/25 p-4 text-sm text-slate-300">
            Query preview: {selectedGenres.join(", ") || "Any genre"} / {STYLE_OPTIONS.find((item) => item.key === style)?.label} / {style === "classic" ? "1900" : yearMin}-{style === "classic" ? Math.min(yearMax, 2005) : yearMax}
          </div>
          <button onClick={run} className="mt-5 w-full rounded-full bg-neon px-5 py-3 text-sm font-bold text-ink transition hover:bg-white">
            Build My Movie Taste
          </button>
        </section>
      </div>

      {loading && <LoadingSkeleton className="h-48 w-full" />}
      {error && <p className="rounded-2xl border border-coral/30 bg-coral/15 px-4 py-3 text-coral">{error}</p>}

      <div className="space-y-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-slate-500">Cold-start output</p>
          <h2 className="mt-2 text-2xl font-black">Your starter recommendations</h2>
        </div>
        {movies.length === 0 && !loading ? (
          <div className="rounded-[1.6rem] border border-dashed border-white/15 bg-white/[0.03] p-8 text-center text-slate-400">
            Complete the three steps and build your starter shelf.
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
