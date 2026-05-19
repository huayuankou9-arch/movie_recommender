import { useEffect, useState } from "react";
import { fetchHome } from "../api/client";
import { HeroBanner } from "../components/HeroBanner";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";
import { HomeResponse } from "../types";

export function Home() {
  const apiMode = import.meta.env.VITE_API_MODE || "static";
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
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold md:text-3xl">Streaming Home</h1>
        <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-300">Mode: {apiMode}</span>
        <input
          type="number"
          value={userId}
          onChange={(e) => setUserId(Number(e.target.value || 1))}
          className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm"
        />
        <button onClick={load} className="rounded-md bg-neon px-4 py-2 text-sm font-semibold text-ink">
          Refresh
        </button>
      </div>
      <p className="text-xs text-slate-400">
        提示：黄色 `Rec` 分数是推荐模型排序分，不是豆瓣/TMDB公开评分；分数越高表示系统越推荐。
      </p>

      {loading && <LoadingSkeleton className="h-[440px] w-full" />}
      {error && <p className="rounded-md bg-coral/20 px-3 py-2 text-sm text-coral">{error}</p>}

      {!loading && data && (
        <div className="space-y-8">
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
