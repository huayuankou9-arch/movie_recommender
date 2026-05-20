import { useEffect, useState } from "react";
import { fetchHome } from "../api/client";
import { HeroBanner } from "../components/HeroBanner";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";
import { HomeResponse } from "../types";

export function Home() {
  const [userId, setUserId] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState<HomeResponse | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await fetchHome(userId));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(`Failed to load home data: ${msg}`);
      console.error("Home load failed", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-10">
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div className="max-w-3xl space-y-2">
          <h1 className="text-3xl font-semibold text-white md:text-5xl">MovieMate: Personalized Movie Discovery</h1>
          <p className="text-sm leading-6 text-slate-300 md:text-base">
            A cinematic recommendation experience powered by collaborative filtering, content signals, and hybrid ranking.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] p-2">
          <span className="px-3 text-xs font-medium uppercase tracking-[0.2em] text-slate-400">Experience as User #</span>
          <input
            type="number"
            min={1}
            value={userId}
            onChange={(e) => setUserId(Number(e.target.value || 1))}
            className="w-24 rounded-full border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-neon"
          />
          <button onClick={load} className="rounded-full bg-neon px-5 py-2 text-sm font-semibold text-ink">
            Refresh
          </button>
        </div>
      </div>

      {loading && <LoadingSkeleton className="h-[480px] w-full" />}
      {error && <p className="rounded-md bg-coral/20 px-3 py-2 text-sm text-coral">{error}</p>}

      {!loading && data && (
        <div className="space-y-10">
          <HeroBanner movie={data.hero_movie} />
          <MovieRow title="For You" movies={data.for_you} />
          <MovieRow title="Because You Like" movies={data.because_you_like} />
          <MovieRow title="Trending Now" movies={data.trending} />
          <MovieRow title="Highly Rated" movies={data.highly_rated} />
          {data.genre_rows.map((row) => (
            <MovieRow key={row.genre} title={`Explore ${row.genre}`} movies={row.movies} />
          ))}
        </div>
      )}
    </div>
  );
}

