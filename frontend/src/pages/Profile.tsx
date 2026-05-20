import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchProfile } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";
import { UserProfile } from "../types";

function StatCard({ label, value, hint }: { label: string; value: string | number; hint: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.055] p-5 shadow-glow backdrop-blur">
      <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-black text-white">{value}</p>
      <p className="mt-2 text-sm text-slate-400">{hint}</p>
    </div>
  );
}

export function Profile() {
  const [userId, setUserId] = useState(1);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setProfile(await fetchProfile(userId));
    } catch {
      setError("We could not assemble this profile yet. Try another user id.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const topGenreText = useMemo(() => profile?.favorite_genres.slice(0, 3).join(" / ") || "Still learning", [profile]);

  return (
    <section className="space-y-8">
      <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(0,224,255,0.22),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.94),rgba(2,6,23,0.78))] p-6 md:p-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-bold uppercase tracking-[0.35em] text-neon">Taste Profile</p>
            <h1 className="mt-3 text-3xl font-black tracking-tight md:text-5xl">Understand the viewer behind the clicks.</h1>
            <p className="mt-4 text-base leading-7 text-slate-300">
              MovieMate turns cached recommendation history into a readable movie taste card: dominant genres, high-confidence titles, and recent signals.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/30 p-4 backdrop-blur">
            <label className="text-xs uppercase tracking-[0.25em] text-slate-400">Experience as User #</label>
            <div className="mt-3 flex gap-2">
              <input
                type="number"
                min={1}
                value={userId}
                onChange={(e) => setUserId(Number(e.target.value || 1))}
                className="w-32 rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm outline-none focus:border-neon"
              />
              <button onClick={load} className="rounded-full bg-neon px-5 py-2 text-sm font-bold text-ink transition hover:bg-white">
                Refresh
              </button>
            </div>
          </div>
        </div>
      </div>

      {loading && <LoadingSkeleton className="h-72" />}
      {error && <p className="rounded-2xl border border-coral/30 bg-coral/15 px-4 py-3 text-coral">{error}</p>}

      {profile && !loading && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatCard label="Signals" value={profile.rating_count} hint="Movies used to sketch this profile" />
            <StatCard label="Avg Rating" value={profile.avg_rating.toFixed(2)} hint="Mean rating signal from cached titles" />
            <StatCard label="Core Taste" value={topGenreText} hint="Most frequent genres in the recommendation stream" />
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold">Genre Affinity</h2>
                  <p className="text-sm text-slate-400">A quick read on what this user tends to enjoy.</p>
                </div>
              </div>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={profile.genre_distribution} margin={{ top: 8, right: 10, left: -18, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="genre" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} contentStyle={{ background: "#0b1220", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 14 }} />
                    <Bar dataKey="count" fill="#00E0FF" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-[1.6rem] border border-neon/20 bg-neon/10 p-5">
              <p className="text-xs font-bold uppercase tracking-[0.28em] text-neon">Profile Summary</p>
              <p className="mt-4 text-lg leading-8 text-cyan-50">{profile.profile_summary}</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {profile.favorite_genres.map((genre) => (
                  <span key={genre} className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-slate-200">
                    {genre}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <MovieRow title="High-Confidence Favorites" movies={profile.top_rated_movies} />
          <MovieRow title="Recent Taste Signals" movies={profile.recent_movies} />
        </div>
      )}
    </section>
  );
}
