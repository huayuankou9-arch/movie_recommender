import { useState } from "react";
import { fetchAlgorithmLab } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";

export function AlgorithmLab() {
  const [userId, setUserId] = useState(1);
  const [topK, setTopK] = useState(12);
  const [weights, setWeights] = useState({
    popularity: 0.1,
    usercf: 0.2,
    itemcf: 0.25,
    mf: 0.3,
    content: 0.15
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<any>(null);

  const updateWeight = (k: keyof typeof weights, v: number) =>
    setWeights((prev) => ({ ...prev, [k]: Number(v.toFixed(2)) }));

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchAlgorithmLab({ user_id: userId, top_k: topK, ...weights });
      setData(res.results);
    } catch (e) {
      setError("Failed to load algorithm lab.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-bold md:text-3xl">Algorithm Lab</h1>
      <div className="space-y-3 rounded-xl border border-white/10 bg-panel p-4">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <input type="number" value={userId} onChange={(e) => setUserId(Number(e.target.value || 1))} className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm" />
          <input type="number" value={topK} onChange={(e) => setTopK(Number(e.target.value || 12))} className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm" />
          <button onClick={load} className="rounded-md bg-neon px-4 py-2 text-sm font-semibold text-ink">
            Compare
          </button>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          {Object.entries(weights).map(([k, v]) => (
            <label key={k} className="text-xs text-slate-300">
              {k}
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={v}
                onChange={(e) => updateWeight(k as keyof typeof weights, Number(e.target.value))}
                className="w-full"
              />
              <span>{v.toFixed(2)}</span>
            </label>
          ))}
        </div>
      </div>
      {loading && <LoadingSkeleton className="h-44" />}
      {error && <p className="rounded-md bg-coral/20 p-3 text-coral">{error}</p>}
      {data && (
        <div className="space-y-8">
          <MovieRow title="Popularity - 热门推荐基线" movies={data.popularity || []} />
          <MovieRow title="UserCF - 相似用户推荐" movies={data.usercf || []} />
          <MovieRow title="ItemCF - 相似电影推荐" movies={data.itemcf || []} />
          <MovieRow title="MF - 隐向量模型推荐" movies={data.mf || []} />
          <MovieRow title="Content - 内容特征推荐" movies={data.content || []} />
          <MovieRow title="Hybrid - 两阶段融合推荐" movies={data.hybrid || []} />
        </div>
      )}
    </section>
  );
}
