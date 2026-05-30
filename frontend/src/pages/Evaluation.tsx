import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchBuildInfo, fetchEvaluation } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { BuildInfo, EvaluationPayload, EvaluationRow } from "../types";

function bestBy(rows: EvaluationRow[], key: keyof EvaluationRow) {
  return rows.reduce<EvaluationRow | null>((best, row) => Number(row[key] || 0) > Number(best?.[key] || -1) ? row : best, null);
}

function fmt(value?: number | null, digits = 4) {
  return value == null || Number.isNaN(Number(value)) ? "-" : Number(value).toFixed(digits);
}

function Card({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.055] p-5 shadow-glow">
      <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-black text-white">{value}</p>
      <p className="mt-2 text-sm leading-6 text-slate-400">{hint}</p>
    </div>
  );
}

function MetricTable({ rows, showErrors = false }: { rows: any[]; showErrors?: boolean }) {
  return (
    <div className="overflow-x-auto rounded-[1.4rem] border border-white/10 bg-black/20 p-4">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="text-slate-300">
          <tr className="border-b border-white/10">
            <th className="py-3">Model</th>
            {showErrors ? <><th>RMSE</th><th>MAE</th></> : <><th>Precision@10</th><th>Recall@10</th><th>HitRate@10</th><th>NDCG@10</th><th>Coverage</th></>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.model} className="border-t border-white/10 hover:bg-white/[0.04]">
              <td className="py-3 font-semibold text-white">{r.model}</td>
              {showErrors ? <><td>{fmt(r.rmse)}</td><td>{fmt(r.mae)}</td></> : <><td>{fmt(r["precision@10"])}</td><td>{fmt(r["recall@10"])}</td><td>{fmt(r["hitrate@10"])}</td><td>{fmt(r["ndcg@10"])}</td><td>{fmt(r.coverage)}</td></>}
            </tr>
          ))}
          {!rows.length && <tr><td className="py-6 text-slate-500" colSpan={showErrors ? 3 : 6}>No metrics exported yet. Run python main.py all to regenerate evaluation data.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function RankingChart({ rows }: { rows: EvaluationRow[] }) {
  const data = rows.map((r) => ({ model: r.model, precision: r["precision@10"], recall: r["recall@10"], hitrate: r["hitrate@10"], ndcg: r["ndcg@10"], coverage: r.coverage }));
  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="model" stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ background: "#0b1220", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 14 }} />
          <Legend />
          <Bar dataKey="precision" fill="#00E0FF" radius={[6, 6, 0, 0]} />
          <Bar dataKey="recall" fill="#FF5D73" radius={[6, 6, 0, 0]} />
          <Bar dataKey="hitrate" fill="#FFCA56" radius={[6, 6, 0, 0]} />
          <Bar dataKey="ndcg" fill="#7DD3FC" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function RankingSection({ title, subtitle, rows }: { title: string; subtitle: string; rows: EvaluationRow[] }) {
  const best = bestBy(rows, "ndcg@10");
  return (
    <section className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
      <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-2xl font-black">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">{subtitle}</p>
        </div>
        <span className="rounded-full border border-neon/20 bg-neon/10 px-3 py-1 text-xs font-bold text-neon">Best NDCG@10: {best?.model || "N/A"}</span>
      </div>
      <RankingChart rows={rows} />
      <div className="mt-5"><MetricTable rows={rows} /></div>
    </section>
  );
}

function hybridWeights(payload: EvaluationPayload | null) {
  const raw = payload?.best_hybrid_weights;
  if (!raw) return { source: "unavailable", weights: {} as Record<string, number> };
  if ("weights" in raw && raw.weights) return { source: raw.source || "tuned", weights: raw.weights };
  return { source: "tuned", weights: raw as Record<string, number> };
}

export function Evaluation() {
  const [payload, setPayload] = useState<EvaluationPayload | null>(null);
  const [buildInfo, setBuildInfo] = useState<BuildInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [metrics, info] = await Promise.all([fetchEvaluation(), fetchBuildInfo()]);
        setPayload(metrics);
        setBuildInfo(info);
      } catch {
        setError("Failed to load evaluation metrics.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const full = payload?.full_ranking || [];
  const randomSampled = payload?.sampled_random || [];
  const popAware = payload?.sampled_popaware || [];
  const rating = payload?.rating_prediction || [];
  const bestRating = useMemo(() => rating.filter((r) => r.rmse != null).sort((a, b) => Number(a.rmse) - Number(b.rmse))[0], [rating]);
  const bestFull = useMemo(() => bestBy(full, "ndcg@10"), [full]);
  const bestRandom = useMemo(() => bestBy(randomSampled, "ndcg@10"), [randomSampled]);
  const bestPopAware = useMemo(() => bestBy(popAware, "ndcg@10"), [popAware]);
  const bestCoverage = useMemo(() => bestBy(full, "coverage"), [full]);
  const meta = payload?.metadata || {};
  const generatedAt = meta.generated_at ? new Date(meta.generated_at).toLocaleString() : buildInfo?.generated_at ? new Date(buildInfo.generated_at).toLocaleString() : "Not available";
  const weightsPayload = hybridWeights(payload);

  if (loading) return <LoadingSkeleton className="h-96" />;
  if (error || !payload) return <p className="rounded-2xl border border-coral/30 bg-coral/15 p-4 text-coral">{error || "No evaluation payload available."}</p>;

  return (
    <section className="space-y-8">
      <div className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(0,224,255,0.18),transparent_32%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,0.82))] p-6 md:p-8">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-neon">Offline Evaluation</p>
        <h1 className="mt-3 text-3xl font-black tracking-tight md:text-5xl">Four evaluation views for one recommender system.</h1>
        <p className="mt-4 max-w-4xl text-base leading-7 text-slate-300">
          Rating prediction measures explicit score accuracy. Full-ranking is the strict whole-catalog task. Random sampled-ranking is useful for fast comparison. Popularity-aware sampled-ranking is harder because negatives are sampled from similarly popular movies.
        </p>
        <div className="mt-5 flex flex-wrap gap-3 text-xs text-slate-400">
          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Generated: {generatedAt}</span>
          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">K: {meta.k ?? 10}</span>
          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Positive rating: {meta.positive_threshold ?? 4}</span>
          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Seed: {meta.seed ?? 42}</span>
          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Pop-aware hard negatives: {meta.popaware_prefer_harder ? "on" : "off"}</span>
          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Evaluated users: full {meta.evaluated_users?.full_ranking ?? full.length}, sampled {meta.evaluated_users?.sampled_popaware ?? randomSampled.length}</span>
          {buildInfo && <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Movies cached: {buildInfo.movies_cached}</span>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Card label="Best Rating Predictor" value={payload.summary?.best_rating_predictor || bestRating?.model || "N/A"} hint="Lowest RMSE / MAE, usually MF/SVD." />
        <Card label="Best Full-ranking Model" value={payload.summary?.best_full_ranking_model || bestFull?.model || "N/A"} hint="Strict whole-catalog NDCG@10." />
        <Card label="Best Random Sampled" value={payload.summary?.best_sampled_random_model || bestRandom?.model || "N/A"} hint="Fast ranking comparison with random negatives." />
        <Card label="Best Pop-aware Sampled" value={payload.summary?.best_sampled_popaware_model || bestPopAware?.model || "N/A"} hint="Harder personalized ranking test." />
        <Card label="Best Coverage" value={payload.summary?.best_coverage_model || bestCoverage?.model || "N/A"} hint={`Largest catalog exposure (${payload.summary?.best_coverage_source || "full_ranking"}).`} />
      </div>

      <section className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
        <h2 className="text-2xl font-black">Rating Prediction</h2>
        <p className="mb-4 mt-1 text-sm leading-6 text-slate-400">RMSE/MAE are mainly meaningful for models that predict explicit 1-5 ratings, especially MF/SVD and UserCF. Popularity, Content, and Hybrid are primarily ranking models.</p>
        <MetricTable rows={rating} showErrors />
      </section>

      <RankingSection title="Full-ranking Evaluation" subtitle="Strict task: each model recommends Top-K from the full unseen catalog. This is closest to production retrieval pressure and usually gives lower scores." rows={full} />
      <RankingSection title="Random Sampled-ranking" subtitle="Each held-out positive competes with random unseen negatives. This is faster and often easier, so popularity baselines can look strong." rows={randomSampled} />
      <RankingSection title="Popularity-aware Sampled-ranking" subtitle="Negatives are sampled from movies with similar train-set popularity. This reduces easy negatives and better tests personalized sorting." rows={popAware} />

      <section className="rounded-[1.6rem] border border-neon/25 bg-neon/10 p-6">
        <p className="text-xs font-bold uppercase tracking-[0.3em] text-neon">Best Hybrid Weights</p>
        <div className="mt-4 flex flex-wrap gap-3">
          {Object.entries(weightsPayload.weights).map(([k, v]) => <span key={k} className="rounded-full border border-white/10 bg-black/25 px-4 py-2 text-sm text-cyan-50">{k}: {Number(v).toFixed(2)}</span>)}
          {!Object.keys(weightsPayload.weights).length && <span className="text-sm text-cyan-100">Weights have not been tuned yet.</span>}
        </div>
        <p className="mt-4 max-w-4xl text-sm leading-7 text-cyan-50">Weight source: <span className="font-bold">{weightsPayload.source}</span>. Hybrid is the fusion framework, but the tables above decide which model wins each evaluation task.</p>
      </section>

      <section className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-6">
        <p className="text-xs font-bold uppercase tracking-[0.3em] text-coral">Experiment Conclusion</p>
        <h2 className="mt-3 text-2xl font-black">Different tasks reward different recommenders.</h2>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <p className="text-sm leading-7 text-slate-300">MF/SVD is the best rating predictor here: <span className="font-bold text-white">{payload.summary?.best_rating_predictor || bestRating?.model || "N/A"}</span> has the lowest RMSE/MAE.</p>
          <p className="text-sm leading-7 text-slate-300">Full-ranking is won by <span className="font-bold text-white">{payload.summary?.best_full_ranking_model || bestFull?.model || "N/A"}</span>; random sampled-ranking is won by <span className="font-bold text-white">{payload.summary?.best_sampled_random_model || bestRandom?.model || "N/A"}</span>.</p>
          <p className="text-sm leading-7 text-slate-300">Popularity-aware sampled-ranking is won by <span className="font-bold text-white">{payload.summary?.best_sampled_popaware_model || bestPopAware?.model || "N/A"}</span>. ItemCF remains the most interpretable model because it supports “Because you liked ...” explanations.</p>
        </div>
        <p className="mt-4 text-sm leading-7 text-slate-400">Hybrid is the overall fusion framework and may dominate some ranking settings, but it should not be presented as best in every metric. This makes the comparison more credible for a course defense.</p>
      </section>
    </section>
  );
}
