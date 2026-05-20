import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { fetchBuildInfo, fetchEvaluation } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { BuildInfo, EvaluationRow } from "../types";

function bestBy(rows: EvaluationRow[], key: keyof EvaluationRow) {
  return rows.reduce<EvaluationRow | null>((best, row) => {
    const value = Number(row[key] || 0);
    const bestValue = best ? Number(best[key] || 0) : -Infinity;
    return value > bestValue ? row : best;
  }, null);
}

function MetricCard({ label, row, value }: { label: string; row: EvaluationRow | null; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.055] p-5 shadow-glow">
      <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-black text-white">{value.toFixed(4)}</p>
      <p className="mt-2 text-sm text-slate-400">{row?.model || "No data"}</p>
    </div>
  );
}

export function Evaluation() {
  const [rows, setRows] = useState<EvaluationRow[]>([]);
  const [buildInfo, setBuildInfo] = useState<BuildInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [metrics, info] = await Promise.all([fetchEvaluation(), fetchBuildInfo()]);
        setRows(metrics);
        setBuildInfo(info);
      } catch {
        setError("Failed to load evaluation metrics.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const bestPrecision = useMemo(() => bestBy(rows, "precision@10"), [rows]);
  const bestRecall = useMemo(() => bestBy(rows, "recall@10"), [rows]);
  const bestNdcg = useMemo(() => bestBy(rows, "ndcg@10"), [rows]);
  const bestCoverage = useMemo(() => bestBy(rows, "coverage"), [rows]);

  const barData = useMemo(
    () =>
      rows.map((r) => ({
        model: r.model,
        precision: r["precision@10"],
        recall: r["recall@10"],
        ndcg: r["ndcg@10"],
        coverage: r.coverage
      })),
    [rows]
  );

  const generatedAt = buildInfo?.generated_at ? new Date(buildInfo.generated_at).toLocaleString() : "Not available";

  if (loading) return <LoadingSkeleton className="h-96" />;
  if (error) return <p className="rounded-2xl border border-coral/30 bg-coral/15 p-4 text-coral">{error}</p>;

  return (
    <section className="space-y-8">
      <div className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(0,224,255,0.18),transparent_32%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,0.82))] p-6 md:p-8">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-neon">Offline Evaluation</p>
        <h1 className="mt-3 text-3xl font-black tracking-tight md:text-5xl">Which recommender performs best?</h1>
        <p className="mt-4 max-w-3xl text-base leading-7 text-slate-300">
          Metrics are computed from MovieLens temporal holdout data. Positive feedback is rating &gt;= 4, and Top-N metrics are measured at K=10.
        </p>
        <div className="mt-5 flex flex-wrap gap-3 text-xs text-slate-400">
          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Generated: {generatedAt}</span>
          {buildInfo && <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Movies cached: {buildInfo.movies_cached}</span>}
          {buildInfo && <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1">Users cached: {buildInfo.users_cached}</span>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <MetricCard label="Best Precision@10" row={bestPrecision} value={Number(bestPrecision?.["precision@10"] || 0)} />
        <MetricCard label="Best Recall@10" row={bestRecall} value={Number(bestRecall?.["recall@10"] || 0)} />
        <MetricCard label="Best NDCG@10" row={bestNdcg} value={Number(bestNdcg?.["ndcg@10"] || 0)} />
        <MetricCard label="Best Coverage" row={bestCoverage} value={Number(bestCoverage?.coverage || 0)} />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
          <h2 className="text-xl font-bold">Ranking Metrics</h2>
          <p className="mb-4 text-sm text-slate-400">Precision, recall, NDCG, and catalog coverage across algorithms.</p>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} margin={{ top: 8, right: 8, left: -16, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="model" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#0b1220", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 14 }} />
                <Legend />
                <Bar dataKey="precision" fill="#00E0FF" radius={[6, 6, 0, 0]} />
                <Bar dataKey="recall" fill="#FF5D73" radius={[6, 6, 0, 0]} />
                <Bar dataKey="ndcg" fill="#FFCA56" radius={[6, 6, 0, 0]} />
                <Bar dataKey="coverage" fill="#7DD3FC" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
          <h2 className="text-xl font-bold">Rating Prediction Error</h2>
          <p className="mb-4 text-sm text-slate-400">Lower RMSE and MAE indicate better explicit rating prediction.</p>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="model" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#0b1220", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 14 }} />
                <Legend />
                <Line type="monotone" dataKey="rmse" stroke="#00E0FF" strokeWidth={3} dot={{ r: 4 }} />
                <Line type="monotone" dataKey="mae" stroke="#FF5D73" strokeWidth={3} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-[1.6rem] border border-white/10 bg-panel/80 p-4">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="text-slate-300">
            <tr className="border-b border-white/10">
              <th className="py-3">Model</th>
              <th>RMSE</th>
              <th>MAE</th>
              <th>Precision@10</th>
              <th>Recall@10</th>
              <th>HitRate@10</th>
              <th>NDCG@10</th>
              <th>Coverage</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.model} className="border-t border-white/10 hover:bg-white/[0.04]">
                <td className="py-3 font-semibold text-white">{r.model}</td>
                <td>{r.rmse.toFixed(4)}</td>
                <td>{r.mae.toFixed(4)}</td>
                <td>{r["precision@10"].toFixed(4)}</td>
                <td>{r["recall@10"].toFixed(4)}</td>
                <td>{r["hitrate@10"].toFixed(4)}</td>
                <td>{r["ndcg@10"].toFixed(4)}</td>
                <td>{r.coverage.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-[1.6rem] border border-neon/25 bg-neon/10 p-6">
        <p className="text-xs font-bold uppercase tracking-[0.3em] text-neon">Experiment Takeaway</p>
        <p className="mt-3 max-w-4xl text-sm leading-7 text-cyan-50">
          Hybrid is the most product-oriented strategy because it does not rely on a single fragile signal. It can inherit the precision of collaborative filtering, the semantic recall of content-based matching, and the coverage benefits of popularity, producing recommendation shelves that are both measurable and explainable.
        </p>
      </div>
    </section>
  );
}
