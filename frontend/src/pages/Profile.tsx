import { useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchProfile } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";
import { UserProfile } from "../types";

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
    } catch (e) {
      setError("Profile not found.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-bold md:text-3xl">My Profile</h1>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={userId}
          onChange={(e) => setUserId(Number(e.target.value || 1))}
          className="rounded-md border border-white/20 bg-black/20 px-3 py-2 text-sm"
        />
        <button onClick={load} className="rounded-md bg-neon px-4 py-2 text-sm font-semibold text-ink">
          Load Profile
        </button>
      </div>
      {loading && <LoadingSkeleton className="h-60" />}
      {error && <p className="rounded-md bg-coral/20 px-3 py-2 text-coral">{error}</p>}
      {profile && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-panel p-4">评分数量: {profile.rating_count}</div>
            <div className="rounded-xl border border-white/10 bg-panel p-4">平均评分: {profile.avg_rating.toFixed(2)}</div>
            <div className="rounded-xl border border-white/10 bg-panel p-4">偏好类型: {profile.favorite_genres.join(", ")}</div>
          </div>
          <div className="h-72 rounded-xl border border-white/10 bg-panel p-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={profile.genre_distribution}>
                <XAxis dataKey="genre" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Bar dataKey="count" fill="#00E0FF" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <MovieRow title="Top Rated Movies" movies={profile.top_rated_movies} />
          <MovieRow title="Recent Movies" movies={profile.recent_movies} />
          <p className="rounded-xl border border-white/10 bg-panel p-4 text-sm text-slate-300">{profile.profile_summary}</p>
        </div>
      )}
    </section>
  );
}
