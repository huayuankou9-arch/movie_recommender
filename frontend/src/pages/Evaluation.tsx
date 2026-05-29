import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchBuildInfo, fetchEvaluation } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { BuildInfo, EvaluationPayload, EvaluationRow } from "../types";

function bestBy(rows: EvaluationRow[], key: keyof EvaluationRow) {
  return rows.reduce<EvaluationRow | null>((best, row) => Number(row[key] || 0) > Number(best?.[key] || -1) ? row : best, null);
}

function Card({ label, value, hint }: { label: string; value: string; hint: string }) {
  return <div className="rounded-2xl border border-white/10 bg-white/[0.055] p-5 shadow-glow"><p className="text-xs uppercase tracking-[0.25em] text-slate-500">{label}</p><p className="mt-2 text-2xl font-black text-white">{value}</p><p className="mt-2 text-sm text-slate-400">{hint}</p></div>;
}

function MetricTable({ rows, showErrors = false }: { rows: any[]; showErrors?: boolean }) {
  return (
    <div className="overflow-x-auto rounded-[1.4rem] border border-white/10 bg-black/20 p-4">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="text-slate-300"><tr className="border-b border-white/10"><th className="py-3">Model</th>{showErrors ? <><th>RMSE</th><th>MAE</th></> : <><th>Precision@10</th><th>Recall@10</th><th>HitRate@10</th><th>NDCG@10</th><th>Coverage</th></>}</tr></thead>
        <tbody>
          {rows.map((r) => <tr key={r.model} className="border-t border-white/10 hover:bg-white/[0.04]"><td className="py-3 font-semibold text-white">{r.model}</td>{showErrors ? <><td>{r.rmse == null ? "-" : r.rmse.toFixed(4)}</td><td>{r.mae == null ? "-" : r.mae.toFixed(4)}</td></> : <><td>{Number(r["precision@10"] || 0).toFixed(4)}</td><td>{Number(r["recall@10"] || 0).toFixed(4)}</td><td>{Number(r["hitrate@10"] || 0).toFixed(4)}</td><td>{Number(r["ndcg@10"] || 0).toFixed(4)}</td><td>{Number(r.coverage || 0).toFixed(4)}</td></>}</tr>)}
        </tbody>
      </table>
    </div>
  );
}

function RankingChart({ rows }: { rows: EvaluationRow[] }) {
  const data = rows.map((r) => ({ model: r.model, precision: r["precision@10"], recall: r["recall@10"], hitrate: r["hitrate@10"], ndcg: r["ndcg@10"], coverage: r.coverage }));
  return <div className="h-80"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" stroke="#1f2937" /><XAxis dataKey="model" stroke="#94a3b8" tick={{ fontSize: 11 }} /><YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} /><Tooltip contentStyle={{ background: "#0b1220", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 14 }} /><Legend /><Bar dataKey="precision" fill="#00E0FF" radius={[6, 6, 0, 0]} /><Bar dataKey="recall" fill="#FF5D73" radius={[6, 6, 0, 0]} /><Bar dataKey="hitrate" fill="#FFCA56" radius={[6, 6, 0, 0]} /><Bar dataKey="ndcg" fill="#7DD3FC" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>;
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
  const sampled = payload?.sampled_ranking || [];
  const rating = payload?.rating_prediction || [];
  const bestRating = useMemo(() => rating.filter((r) => r.rmse != null).sort((a, b) => Number(a.rmse) - Number(b.rmse))[0], [rating]);
  const bestFull = useMemo(() => bestBy(full, "ndcg@10"), [full]);
  const bestSampled = useMemo(() => bestBy(sampled, "ndcg@10"), [sampled]);
  const bestCoverage = useMemo(() => bestBy(full, "coverage"), [full]);
  const generatedAt = buildInfo?.generated_at ? new Date(buildInfo.generated_at).toLocaleString() : "Not available";

  if (loading) return <LoadingSkeleton className="h-96" />;
  if (error || !payload) return <p className="rounded-2xl border border-coral/30 bg-coral/15 p-4 text-coral">{error || "No evaluation payload available."}</p>;

  return (
    <section className="space-y-8">
      <div className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(0,224,255,0.18),transparent_32%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,0.82))] p-6 md:p-8">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-neon">Offline Evaluation</p>
        <h1 className="mt-3 text-3xl font-black tracking-tight md:text-5xl">Strict ranking, sampled ranking, and rating prediction.</h1>
        <p className="mt-4 max-w-4xl text-base leading-7 text-slate-300">Full-ranking evaluates against the whole catalog. Sampled-ranking compares held-out positives against sampled negatives. RMSE/MAE are emphasized only for models that predict explicit ratings.</p>
        <div className="mt-5 flex flex-wrap gap-3 text-xs text-slate-400"><span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Generated: {generatedAt}</span>{buildInfo && <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Movies cached: {buildInfo.movies_cached}</span>}</div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card label="Best Rating Predictor" value={bestRating?.model || "N/A"} hint="Lowest RMSE / MAE" />
        <Card label="Best Interpretable Recommender" value="ItemCF" hint="Source-movie explanations" />
        <Card label="Best Overall Ranker" value={bestSampled?.model || "Hybrid"} hint="Sampled NDCG@10 leader" />
        <Card label="Best Coverage" value={bestCoverage?.model || "N/A"} hint="Largest catalog exposure" />
      </div>

      <section className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5"><h2 className="text-2xl font-black">Rating Prediction</h2><p className="mb-4 mt-1 text-sm text-slate-400">RMSE/MAE are mainly meaningful for MF/SVD, UserCF, and optionally ItemCF.</p><MetricTable rows={rating} showErrors /></section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-2"><div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5"><h2 className="text-2xl font-black">Full-ranking Evaluation</h2><p className="mb-4 mt-1 text-sm text-slate-400">Strict: each model recommends from the full movie catalog.</p><RankingChart rows={full} /></div><div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5"><h2 className="text-2xl font-black">Sampled-ranking Evaluation</h2><p className="mb-4 mt-1 text-sm text-slate-400">Held-out positives are ranked against sampled negatives to compare ranking ability.</p><RankingChart rows={sampled} /></div></section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-2"><div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5"><h2 className="text-xl font-bold">Full-ranking Table</h2><MetricTable rows={full} /></div><div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5"><h2 className="text-xl font-bold">Sampled-ranking Table</h2><MetricTable rows={sampled} /></div></section>

      <section className="rounded-[1.6rem] border border-neon/25 bg-neon/10 p-6"><p className="text-xs font-bold uppercase tracking-[0.3em] text-neon">Best Hybrid Weights</p><div className="mt-4 flex flex-wrap gap-3">{Object.entries(payload.best_hybrid_weights || {}).map(([k, v]) => <span key={k} className="rounded-full border border-white/10 bg-black/25 px-4 py-2 text-sm text-cyan-50">{k}: {Number(v).toFixed(2)}</span>)}</div><p className="mt-4 max-w-4xl text-sm leading-7 text-cyan-50">Hybrid is designed to be the best overall ranker by combining ItemCF's explainability, MF's rating prediction, Content's semantic matching, UserCF's neighbor evidence, and Popularity's cold-start stability.</p></section>
    </section>
  );
}
