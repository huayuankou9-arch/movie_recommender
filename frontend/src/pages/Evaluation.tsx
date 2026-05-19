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
import { fetchEvaluation } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { EvaluationRow } from "../types";

export function Evaluation() {
  const [rows, setRows] = useState<EvaluationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        setRows(await fetchEvaluation());
      } catch (e) {
        setError("Failed to load evaluation metrics.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

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

  if (loading) return <LoadingSkeleton className="h-80" />;
  if (error) return <p className="rounded-md bg-coral/20 p-3 text-coral">{error}</p>;

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-bold md:text-3xl">Evaluation</h1>
      <div className="overflow-x-auto rounded-xl border border-white/10 bg-panel p-3">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="text-slate-300">
            <tr>
              <th>Model</th>
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
              <tr key={r.model} className="border-t border-white/10">
                <td className="py-2">{r.model}</td>
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="h-80 rounded-xl border border-white/10 bg-panel p-3">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="model" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip />
              <Legend />
              <Bar dataKey="precision" fill="#00E0FF" />
              <Bar dataKey="recall" fill="#FF5D73" />
              <Bar dataKey="ndcg" fill="#FFCA56" />
              <Bar dataKey="coverage" fill="#38bdf8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="h-80 rounded-xl border border-white/10 bg-panel p-3">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="model" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="rmse" stroke="#00E0FF" strokeWidth={2} />
              <Line type="monotone" dataKey="mae" stroke="#FF5D73" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <p className="rounded-xl border border-neon/30 bg-neon/10 p-4 text-sm text-cyan-100">
        Hybrid 模型在排序指标上通常更稳健，因为它融合了热门信号、协同过滤信号和内容语义信号，能兼顾准确率与覆盖率。
      </p>
    </section>
  );
}
