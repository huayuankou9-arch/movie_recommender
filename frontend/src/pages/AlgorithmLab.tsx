import { useEffect, useMemo, useState } from "react";
import { fetchAlgorithmLab, fetchEvaluation } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";
import { MovieCard } from "../types";

const ALGORITHM_COPY: Record<string, { title: string; subtitle: string; note: string; classroom: string }> = {
  popularity: {
    title: "Popularity",
    subtitle: "A reliable cold-start baseline",
    note: "Ranks movies by a weighted blend of average rating and rating volume.",
    classroom: "Non-personalized baseline: useful for cold start, weak for individual taste."
  },
  usercf: {
    title: "UserCF",
    subtitle: "People with similar taste also liked...",
    note: "Finds neighboring users by cosine similarity and recommends movies that those neighbors rated highly.",
    classroom: "Neighborhood CF over users: explains recommendations by similar people."
  },
  itemcf: {
    title: "ItemCF",
    subtitle: "Because you liked a related movie",
    note: "Uses the user's rated movies to surface items that are similar in the collaborative rating matrix.",
    classroom: "Neighborhood CF over items: stable and easy to explain with source movies."
  },
  mf: {
    title: "MF / SVD",
    subtitle: "Latent taste prediction",
    note: "Projects users and movies into latent factors and predicts ratings from hidden preference dimensions.",
    classroom: "Model-based CF: often stronger prediction, less directly interpretable."
  },
  content: {
    title: "Content-based",
    subtitle: "Story, genre, cast, tags, and keywords",
    note: "Uses TF-IDF metadata similarity to recommend movies with related content signals.",
    classroom: "Content matching: works for new items and produces semantic explanations."
  },
  hybrid: {
    title: "Hybrid",
    subtitle: "Two-stage recall and weighted ranking",
    note: "Blends popularity, collaborative filtering, matrix factorization, and content signals.",
    classroom: "Hybrid ranking: balances accuracy, coverage, diversity, and interpretability."
  }
};

const ORDER = ["popularity", "usercf", "itemcf", "mf", "content", "hybrid"];
type WeightKey = "popularity" | "usercf" | "itemcf" | "mf" | "content";

function overlapWithHybrid(results: Record<string, MovieCard[]> | null, key: string) {
  if (!results || key === "hybrid") return "Hybrid is the reference blend.";
  const hybridIds = new Set((results.hybrid || []).map((m) => m.movieId));
  const ids = (results[key] || []).map((m) => m.movieId);
  const overlap = ids.filter((id) => hybridIds.has(id)).length;
  return `${overlap} of ${ids.length} titles also appear in Hybrid.`;
}

function modelScore(movie: MovieCard | undefined, key: string) {
  if (!movie) return null;
  const breakdown = movie.score_breakdown || {};
  const mapped = key === "mf" ? breakdown.mf : key === "itemcf" ? breakdown.itemcf : key === "content" ? breakdown.content : key === "popularity" ? breakdown.popularity : key === "usercf" ? breakdown.usercf : breakdown.recommendation;
  if (typeof mapped === "number") return mapped;
  if (typeof movie.score === "number") return movie.score;
  if (typeof movie.rating_avg === "number") return movie.rating_avg;
  return null;
}

export function AlgorithmLab() {
  const [userId, setUserId] = useState(1);
  const [topK, setTopK] = useState(12);
  const [weights, setWeights] = useState<Record<WeightKey, number>>({ popularity: 0.1, usercf: 0.2, itemcf: 0.25, mf: 0.3, content: 0.15 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<Record<string, MovieCard[]> | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [bestWeights, setBestWeights] = useState<Record<string, number>>({});
  const [hybridStatus, setHybridStatus] = useState("");

  const totalWeight = useMemo(() => Object.values(weights).reduce((sum, x) => sum + x, 0), [weights]);
  const allMovies = useMemo(() => {
    const map = new Map<number, MovieCard>();
    for (const key of ORDER) {
      for (const movie of data?.[key] || []) {
        if (!map.has(movie.movieId)) map.set(movie.movieId, movie);
      }
    }
    return Array.from(map.values());
  }, [data]);

  useEffect(() => {
    if (!selectedId && allMovies.length) setSelectedId(allMovies[0].movieId);
  }, [allMovies, selectedId]);

  const updateWeight = (k: WeightKey, v: number) => setWeights((prev) => ({ ...prev, [k]: Number(v.toFixed(2)) }));

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchAlgorithmLab({ user_id: userId, top_k: topK, ...weights });
      setData(res.results);
      setSelectedId(null);
    } catch {
      setError("Failed to load algorithm comparison. Static cache may need to be regenerated.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    fetchEvaluation()
      .then((payload) => {
        setBestWeights(payload.best_hybrid_weights || {});
        const sampled = payload.sampled_popaware || payload.sampled_random || payload.sampled_ranking || [];
        const hybrid = sampled.find((row) => row.model === "Hybrid");
        const itemcf = sampled.find((row) => row.model === "ItemCF");
        if (hybrid && itemcf && Number(hybrid["ndcg@10"] || 0) >= Number(itemcf["ndcg@10"] || 0)) {
          setHybridStatus("Hybrid achieves the best popularity-aware sampled-ranking NDCG@10 or matches the strongest ItemCF baseline.");
        } else if (hybrid && itemcf) {
          setHybridStatus("Hybrid is close to ItemCF; continue tuning validation weights for higher popularity-aware sampled NDCG@10.");
        }
      })
      .catch(() => undefined);
  }, []);

  const selectedMovie = allMovies.find((m) => m.movieId === selectedId) || null;

  return (
    <section className="space-y-8">
      <div className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(255,93,115,0.2),transparent_30%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,0.82))] p-6 md:p-8">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-coral">Recommendation Systems Lab</p>
        <div className="mt-3 grid gap-5 lg:grid-cols-[1fr_420px] lg:items-end">
          <div>
            <h1 className="text-3xl font-black tracking-tight md:text-5xl">Compare every recommender, side by side.</h1>
            <p className="mt-4 max-w-3xl text-base leading-7 text-slate-300">
              A course-defense view of how baseline, neighborhood CF, matrix factorization, content matching, and hybrid ranking behave differently.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/30 p-4 backdrop-blur">
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs uppercase tracking-[0.22em] text-slate-400">
                User
                <input type="number" min={1} value={userId} onChange={(e) => setUserId(Number(e.target.value || 1))} className="mt-2 w-full rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm normal-case tracking-normal outline-none focus:border-neon" />
              </label>
              <label className="text-xs uppercase tracking-[0.22em] text-slate-400">
                Top-K
                <input type="number" min={4} max={30} value={topK} onChange={(e) => setTopK(Number(e.target.value || 12))} className="mt-2 w-full rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm normal-case tracking-normal outline-none focus:border-neon" />
              </label>
            </div>
            <button onClick={load} className="mt-4 w-full rounded-full bg-neon px-5 py-2.5 text-sm font-bold text-ink transition hover:bg-white">Run Comparison</button>
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-xl font-bold">Hybrid Weight Mixer</h2>
              <p className="text-sm text-slate-400">Adjust the ranking blend for classroom experimentation. Current total: {totalWeight.toFixed(2)}</p>
            </div>
            <p className="text-xs text-slate-500">The shelves below use cached model outputs; the sliders document the ranking formula.</p>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-5">
            {(Object.keys(weights) as WeightKey[]).map((k) => (
              <label key={k} className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-300">
                <span className="flex items-center justify-between font-semibold text-white">{k.toUpperCase()}<span className="text-neon">{weights[k].toFixed(2)}</span></span>
                <input type="range" min={0} max={1} step={0.05} value={weights[k]} onChange={(e) => updateWeight(k, Number(e.target.value))} className="mt-4 w-full accent-cyan-300" />
              </label>
            ))}
          </div>
        </div>

        <div className="rounded-[1.6rem] border border-coral/25 bg-coral/10 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-coral">Why algorithms differ?</p>
          <p className="mt-3 text-sm leading-7 text-rose-50">
            Each model sees a different slice of evidence: popularity sees the crowd, UserCF sees similar people, ItemCF sees related titles, MF sees latent factors, and Content sees metadata. Hybrid combines them to reduce blind spots.
          </p>
        </div>
      </div>

      <div className="rounded-[1.6rem] border border-neon/25 bg-neon/10 p-5">
        <p className="text-xs font-bold uppercase tracking-[0.28em] text-neon">Why Hybrid improves ranking?</p>
        <p className="mt-3 text-sm leading-7 text-cyan-50">
          Hybrid uses validation-tuned weights to combine calibrated model evidence. ItemCF gives explainable source-movie signals, MF estimates latent preference, Content adds semantic recall, UserCF adds similar-user evidence, and Popularity protects cold-start stability.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {Object.entries(bestWeights).map(([key, value]) => (
            <span key={key} className="rounded-full border border-white/10 bg-black/25 px-3 py-1 text-xs text-cyan-50">
              {key}: {Number(value).toFixed(2)}
            </span>
          ))}
        </div>
        {hybridStatus && <p className="mt-3 text-sm text-cyan-100">{hybridStatus}</p>}
      </div>

      {loading && <LoadingSkeleton className="h-56" />}
      {error && <p className="rounded-2xl border border-coral/30 bg-coral/15 p-4 text-coral">{error}</p>}

      {data && selectedMovie && (
        <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
          <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.28em] text-neon">Inspect one movie</p>
              <select value={selectedId || ""} onChange={(e) => setSelectedId(Number(e.target.value))} className="mt-3 w-full rounded-2xl border border-white/15 bg-black/30 px-4 py-3 text-sm text-white outline-none focus:border-neon">
                {allMovies.map((movie) => (
                  <option key={movie.movieId} value={movie.movieId}>{movie.title}</option>
                ))}
              </select>
              <p className="mt-3 text-sm text-slate-400">Selected: {selectedMovie.title}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
              {ORDER.map((key) => {
                const movie = data[key]?.find((m) => m.movieId === selectedId);
                const score = modelScore(movie, key);
                return (
                  <div key={key} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">{ALGORITHM_COPY[key].title}</p>
                    <p className="mt-2 text-2xl font-black text-white">{score == null ? "-" : score.toFixed(score > 10 ? 0 : 3)}</p>
                    <p className="mt-1 line-clamp-2 text-[11px] text-slate-500">{movie?.reason || "Not in this model's Top-K"}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {data && (
        <div className="space-y-10">
          {ORDER.map((key) => {
            const copy = ALGORITHM_COPY[key];
            return (
              <div key={key} className="rounded-[1.6rem] border border-white/10 bg-white/[0.035] p-4 md:p-5">
                <div className="mb-4 grid gap-3 md:grid-cols-[280px_1fr] md:items-end">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.28em] text-neon">{copy.subtitle}</p>
                    <h2 className="mt-2 text-2xl font-black">{copy.title}</h2>
                  </div>
                  <div>
                    <p className="text-sm leading-6 text-slate-300">{copy.note}</p>
                    <p className="mt-1 text-xs text-slate-400">{copy.classroom}</p>
                    <p className="mt-2 text-xs text-slate-500">{overlapWithHybrid(data, key)}</p>
                  </div>
                </div>
                <MovieRow title={`${copy.title} Recommendations`} movies={data[key] || []} />
              </div>
            );
          })}
        </div>
      )}

      <div className="rounded-[1.6rem] border border-neon/25 bg-neon/10 p-6">
        <p className="text-xs font-bold uppercase tracking-[0.3em] text-neon">Why Hybrid?</p>
        <h2 className="mt-3 text-2xl font-black text-white">Accuracy, explanations, and variety rarely come from one signal.</h2>
        <p className="mt-3 max-w-4xl text-sm leading-7 text-cyan-50">
          Popularity protects cold-start reliability, UserCF and ItemCF provide collaborative taste evidence, MF/SVD improves personalized rating prediction, and Content-based matching keeps recommendations explainable. Hybrid merges these strengths so the final shelf feels less brittle than any single model.
        </p>
      </div>
    </section>
  );
}
