import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchProfile } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieRow } from "../components/MovieRow";
import { MovieCard, UserProfile } from "../types";

function StatCard({ label, value, hint }: { label: string; value: string | number; hint: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.055] p-5 shadow-glow backdrop-blur">
      <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-black text-white md:text-3xl">{value}</p>
      <p className="mt-2 text-sm text-slate-400">{hint}</p>
    </div>
  );
}

function collectTasteTags(movies: MovieCard[]) {
  const tags = new Map<string, number>();
  for (const movie of movies) {
    const reviewTags = Array.isArray(movie.reviews) ? movie.reviews.map((r) => r.text) : [];
    const genreTags = (movie.genres || "").split(",");
    [...reviewTags, ...genreTags]
      .map((x) => String(x || "").trim())
      .filter((x) => x && x.length < 28)
      .forEach((x) => tags.set(x, (tags.get(x) || 0) + 1));
  }
  return Array.from(tags.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 14)
    .map(([tag]) => tag);
}

function buildSummary(profile: UserProfile) {
  const top = profile.genre_distribution.slice(0, 3);
  if (!top.length) return profile.profile_summary;
  const [first, second, third] = top;
  const total = profile.genre_distribution.reduce((sum, item) => sum + item.count, 0) || 1;
  const focus = Math.round((first.count / total) * 100);
  const supporting = [second?.genre, third?.genre].filter(Boolean).join(" and ");
  return `User #${profile.userId} shows a clear preference for ${first.genre}, which accounts for about ${focus}% of observed recommendation signals${supporting ? `, with ${supporting} as supporting tastes` : ""}. The profile suggests a viewer who responds to ${profile.avg_rating >= 4 ? "highly rated" : "varied"} movies with recognizable genre patterns.`;
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
  const allProfileMovies = useMemo(() => (profile ? [...profile.top_rated_movies, ...profile.recent_movies] : []), [profile]);
  const tasteTags = useMemo(() => collectTasteTags(allProfileMovies), [allProfileMovies]);
  const stability = useMemo(() => {
    if (!profile?.genre_distribution.length) return "Learning";
    const total = profile.genre_distribution.reduce((sum, item) => sum + item.count, 0) || 1;
    const topShare = profile.genre_distribution[0].count / total;
    if (profile.rating_count >= 24 && topShare >= 0.28) return "High";
    if (profile.rating_count >= 12) return "Medium";
    return "Exploratory";
  }, [profile]);

  return (
    <section className="space-y-8">
      <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(0,224,255,0.22),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.94),rgba(2,6,23,0.78))] p-6 md:p-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-bold uppercase tracking-[0.35em] text-neon">User Taste Dashboard</p>
            <h1 className="mt-3 text-3xl font-black tracking-tight md:text-5xl">A readable profile behind the recommendations.</h1>
            <p className="mt-4 text-base leading-7 text-slate-300">
              This dashboard explains the user in product language: what genres dominate, which tags describe their taste, and how stable the signals are.
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
          <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
            <StatCard label="User ID" value={`#${profile.userId}`} hint="Current viewer profile" />
            <StatCard label="Rating Signals" value={profile.rating_count} hint="Movies used to sketch taste" />
            <StatCard label="Avg Rating" value={profile.avg_rating.toFixed(2)} hint="Mean rating signal" />
            <StatCard label="Favorite Genre" value={profile.favorite_genres[0] || "Learning"} hint="Top genre affinity" />
            <StatCard label="Stability" value={stability} hint="How consistent the taste pattern is" />
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-5">
              <div className="rounded-[1.6rem] border border-neon/20 bg-neon/10 p-5">
                <p className="text-xs font-bold uppercase tracking-[0.28em] text-neon">Profile Summary</p>
                <p className="mt-4 text-lg leading-8 text-cyan-50">{buildSummary(profile)}</p>
              </div>

              <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
                <h2 className="text-xl font-bold">Favorite Genres</h2>
                <div className="mt-4 flex flex-wrap gap-2">
                  {profile.favorite_genres.map((genre) => (
                    <span key={genre} className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-sm text-slate-200">
                      {genre}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
                <h2 className="text-xl font-bold">Taste Tags</h2>
                <p className="mt-1 text-sm text-slate-400">Derived from MovieLens tags, genre labels, and high-confidence recommendation context.</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {tasteTags.map((tag) => (
                    <span key={tag} className="rounded-full border border-coral/20 bg-coral/10 px-3 py-1 text-xs text-rose-100">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="rounded-[1.6rem] border border-white/10 bg-panel/80 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold">Genre Preference Chart</h2>
                  <p className="text-sm text-slate-400">Counts by genre from cached recommendation and history signals.</p>
                </div>
              </div>
              <div className="h-96">
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
          </div>

          <MovieRow title="My High-Rated Movie Wall" movies={profile.top_rated_movies} />
          <MovieRow title="Recently Rated Movies" movies={profile.recent_movies} />

          <div className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-6">
            <p className="text-xs font-bold uppercase tracking-[0.3em] text-neon">How we understand this user</p>
            <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-300">
              MovieMate builds this taste profile from high-rated movie genres, similar-user behavior, movie tags, and recent interaction history. Collaborative signals explain what neighboring users enjoy, while content signals explain the genres, themes, and story traits that make recommendations understandable.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
