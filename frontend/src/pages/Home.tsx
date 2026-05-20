import { useEffect, useMemo, useState } from "react";
import { fetchHome, fetchProfile } from "../api/client";
import { HeroBanner } from "../components/HeroBanner";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { MovieCard } from "../components/MovieCard";
import { MovieRow } from "../components/MovieRow";
import { HomeResponse, MovieCard as Movie, UserProfile } from "../types";
import { PLACEHOLDER_POSTER, sanitizePosterUrl, sanitizeTitle } from "../utils/movie";

function SourceMoviePanel({ source }: { source: Partial<Movie> | null }) {
  if (!source) return null;
  const title = sanitizeTitle(source.title) || "a favorite movie";
  const poster = sanitizePosterUrl(source.poster_url) || PLACEHOLDER_POSTER;
  return (
    <aside className="rounded-[1.4rem] border border-neon/20 bg-neon/10 p-4">
      <p className="text-xs font-bold uppercase tracking-[0.25em] text-neon">Source Movie</p>
      <div className="mt-4 flex gap-3 lg:block">
        <img
          src={poster}
          alt={title}
          className="h-28 w-20 rounded-xl object-cover lg:h-64 lg:w-full"
          onError={(e) => {
            e.currentTarget.src = PLACEHOLDER_POSTER;
          }}
        />
        <div className="mt-0 lg:mt-3">
          <h3 className="line-clamp-2 text-lg font-black text-white">{title}</h3>
          <p className="mt-1 text-xs text-slate-400">{source.year || ""} {source.genres ? `/ ${source.genres}` : ""}</p>
          <p className="mt-3 text-sm leading-6 text-cyan-50">We use this high-confidence signal to retrieve movies with similar audience or story patterns.</p>
        </div>
      </div>
    </aside>
  );
}

function BecauseYouLikeSection({ movies, fallbackSource }: { movies: Movie[]; fallbackSource: Partial<Movie> | null }) {
  const source = movies.find((m) => m.source_movie)?.source_movie || fallbackSource;
  const displayMovies = movies.map((movie) => ({ ...movie, source_movie: movie.source_movie || source }));
  if (!displayMovies.length) return null;
  const sourceTitle = sanitizeTitle(source?.title) || "one of your favorites";

  return (
    <section className="space-y-3">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.28em] text-slate-500">Recommendation explanation</p>
        <h2 className="mt-2 text-xl font-black text-white md:text-2xl">Because you liked {sourceTitle}</h2>
      </div>
      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        <SourceMoviePanel source={source || null} />
        <div className="movie-row-scrollbar flex gap-4 overflow-x-auto pb-3">
          {displayMovies.map((movie) => (
            <MovieCard key={`because-${movie.movieId}`} movie={movie} />
          ))}
        </div>
      </div>
    </section>
  );
}

export function Home() {
  const [userId, setUserId] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState<HomeResponse | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [homeData, profileData] = await Promise.all([fetchHome(userId), fetchProfile(userId).catch(() => null)]);
      setData(homeData);
      setProfile(profileData);
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

  const sourceFallback = useMemo(() => {
    if (profile?.top_rated_movies?.length) return profile.top_rated_movies[0];
    if (data?.for_you?.length) return data.for_you[0];
    if (data?.highly_rated?.length) return data.highly_rated[0];
    return null;
  }, [profile, data]);

  return (
    <div className="space-y-10">
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div className="max-w-3xl space-y-2">
          <h1 className="text-3xl font-semibold text-white md:text-5xl">MovieMate: Personalized Movie Discovery</h1>
          <p className="text-sm leading-6 text-slate-300 md:text-base">
            A cinematic recommendation experience powered by collaborative filtering, content signals, and hybrid ranking.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] p-2">
          <span className="px-3 text-xs font-medium uppercase tracking-[0.2em] text-slate-400">Experience as User #</span>
          <input
            type="number"
            min={1}
            value={userId}
            onChange={(e) => setUserId(Number(e.target.value || 1))}
            className="w-24 rounded-full border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-neon"
          />
          <button onClick={load} className="rounded-full bg-neon px-5 py-2 text-sm font-semibold text-ink transition hover:bg-white">
            Refresh
          </button>
        </div>
      </div>

      {loading && <LoadingSkeleton className="h-[480px] w-full" />}
      {error && <p className="rounded-md bg-coral/20 px-3 py-2 text-sm text-coral">{error}</p>}

      {!loading && data && (
        <div className="space-y-10">
          <HeroBanner movie={data.hero_movie} />
          <MovieRow title="For You" movies={data.for_you} />
          <BecauseYouLikeSection movies={data.because_you_like.length ? data.because_you_like : data.for_you.slice(1, 13)} fallbackSource={sourceFallback} />
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
