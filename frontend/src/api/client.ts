import axios from "axios";
import { EvaluationRow, HomeResponse, MovieCard, UserProfile } from "../types";
import {
  PLACEHOLDER_POSTER,
  isDisplayableMovie,
  sanitizeBackdropUrl,
  sanitizePosterUrl,
  sanitizeTitle
} from "../utils/movie";

const API_MODE = import.meta.env.VITE_API_MODE || "static";
const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const BASE_URL = import.meta.env.BASE_URL || "/";
const STATIC_DATA_BASE = `${BASE_URL}data/`;

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 20000
});

type RecoCache = {
  users?: Record<string, Record<string, MovieCard[]>>;
  home_cache?: Record<string, HomeResponse>;
  similar_by_movie?: Record<string, Record<string, MovieCard[]>>;
};

const memoryCache = new Map<string, unknown>();

async function readStaticJson<T>(name: string): Promise<T> {
  if (memoryCache.has(name)) return memoryCache.get(name) as T;
  const resp = await fetch(`${STATIC_DATA_BASE}${name}`, { cache: "no-store" });
  if (!resp.ok) throw new Error(`Failed to load static data: ${name}`);
  const data = (await resp.json()) as T;
  memoryCache.set(name, data);
  return data;
}

function normalizeMovieCard(m: Partial<MovieCard>): MovieCard {
  return {
    movieId: Number(m.movieId || 0),
    title: sanitizeTitle(m.title) || "Unknown Movie",
    year: m.year ?? null,
    genres: m.genres || "",
    poster_url: sanitizePosterUrl(m.poster_url),
    backdrop_url: sanitizeBackdropUrl(m.backdrop_url),
    overview: typeof m.overview === "string" ? m.overview : "",
    score: typeof m.score === "number" ? m.score : undefined,
    reason: typeof m.reason === "string" ? m.reason : "",
    rating_avg: typeof m.rating_avg === "number" ? m.rating_avg : null,
    rating_count: typeof m.rating_count === "number" ? m.rating_count : null,
    review_snippet: typeof m.review_snippet === "string" ? m.review_snippet : "",
    reviews: Array.isArray(m.reviews) ? m.reviews : []
  };
}

function normalizeMovieList(items: Array<Partial<MovieCard>>): MovieCard[] {
  return (items || [])
    .map(normalizeMovieCard)
    .filter((m) => isDisplayableMovie(m))
    .map((m) => ({ ...m, poster_url: m.poster_url || PLACEHOLDER_POSTER }));
}

function fallbackHome(homeMap: Record<string, HomeResponse>, userId: number): HomeResponse {
  const byUser = homeMap[String(userId)];
  if (byUser) return byUser;
  const first = Object.values(homeMap)[0];
  if (first) return first;
  return {
    hero_movie: null,
    for_you: [],
    trending: [],
    highly_rated: [],
    because_you_like: [],
    genre_rows: []
  };
}

function normalizeHomePayload(home: HomeResponse): HomeResponse {
  const forYou = normalizeMovieList(home.for_you || []);
  const trending = normalizeMovieList(home.trending || []);
  const highlyRated = normalizeMovieList(home.highly_rated || []);
  const becauseYouLike = normalizeMovieList(home.because_you_like || []);
  const genreRows = (home.genre_rows || [])
    .map((row) => ({
      genre: row.genre,
      movies: normalizeMovieList(row.movies || [])
    }))
    .filter((row) => row.movies.length > 0);

  let hero = home.hero_movie ? normalizeMovieCard(home.hero_movie) : null;
  if (!hero || !isDisplayableMovie(hero)) {
    hero = forYou[0] || trending[0] || highlyRated[0] || becauseYouLike[0] || null;
  }

  return {
    ...home,
    hero_movie: hero,
    for_you: forYou,
    trending,
    highly_rated: highlyRated,
    because_you_like: becauseYouLike,
    genre_rows: genreRows
  };
}

function similarFromMovies(allMovies: MovieCard[], movieId: number, topK: number): MovieCard[] {
  const target = allMovies.find((m) => m.movieId === movieId);
  if (!target) return allMovies.slice(0, topK).map(normalizeMovieCard);
  const targetGenres = (target.genres || "")
    .split(",")
    .map((g) => g.trim().toLowerCase())
    .filter(Boolean);
  const scored = allMovies
    .filter((m) => m.movieId !== movieId)
    .map((m) => {
      const movieGenres = (m.genres || "")
        .split(",")
        .map((g) => g.trim().toLowerCase())
        .filter(Boolean);
      const overlap = movieGenres.filter((g) => targetGenres.includes(g)).length;
      const ratingBoost = typeof m.rating_avg === "number" ? m.rating_avg : 0;
      return { movie: m, score: overlap * 10 + ratingBoost };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, topK)
    .map((x) => ({ ...x.movie, reason: "内容和类型与你当前电影相似" }));
  return normalizeMovieList(scored);
}

export const fetchHome = async (userId: number) => {
  if (API_MODE === "backend") {
    const { data } = await api.get<HomeResponse>("/home", { params: { user_id: userId } });
    return normalizeHomePayload(data);
  }
  const homeMap = await readStaticJson<Record<string, HomeResponse>>("home_cache.json");
  return normalizeHomePayload(fallbackHome(homeMap, userId));
};

export const fetchRecommend = async (userId: number, model: string, topK = 12) => {
  if (API_MODE === "backend") {
    const { data } = await api.get<{ items: MovieCard[] }>(`/recommend/${userId}`, {
      params: { model, top_k: topK }
    });
    return normalizeMovieList(data.items || []).slice(0, topK);
  }
  const recCache = await readStaticJson<RecoCache>("recommendations_cache.json");
  const userData = recCache.users?.[String(userId)] || {};
  const byModel = userData[model] || userData.hybrid || [];
  if (byModel.length) return normalizeMovieList(byModel).slice(0, topK);
  const home = await fetchHome(userId);
  return (home.for_you || []).slice(0, topK).map(normalizeMovieCard);
};

export const fetchProfile = async (userId: number) => {
  if (API_MODE === "backend") {
    const { data } = await api.get<UserProfile>(`/users/${userId}/profile`);
    return data;
  }
  const home = await fetchHome(userId);
  const pool = [...home.for_you, ...home.because_you_like, ...home.trending].slice(0, 24);
  const genreCount = new Map<string, number>();
  for (const m of pool) {
    (m.genres || "")
      .split(",")
      .map((g) => g.trim())
      .filter(Boolean)
      .forEach((g) => genreCount.set(g, (genreCount.get(g) || 0) + 1));
  }
  const genre_distribution = Array.from(genreCount.entries())
    .map(([genre, count]) => ({ genre, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);
  return {
    userId,
    rating_count: pool.length,
    avg_rating: 4.2,
    favorite_genres: genre_distribution.slice(0, 5).map((x) => x.genre),
    genre_distribution,
    top_rated_movies: pool.slice(0, 12).map((m, i) => ({ ...m, rating: 5 - (i % 3) * 0.5 })),
    recent_movies: pool.slice(12, 24).map((m, i) => ({ ...m, rating: 4.5 - (i % 2) * 0.5 })),
    profile_summary: "静态演示模式：该画像来自缓存推荐结果。"
  };
};

export const fetchMovieDetail = async (movieId: number) => {
  if (API_MODE === "backend") {
    const { data } = await api.get(`/movies/${movieId}`);
    return {
      ...data,
      ...normalizeMovieCard(data),
      similar_movies: normalizeMovieList(data?.similar_movies || [])
    };
  }
  const movies = normalizeMovieList(await readStaticJson<MovieCard[]>("movies.json"));
  const movie = movies.find((m) => Number(m.movieId) === movieId);
  if (!movie) throw new Error("Movie not found");
  const similar = similarFromMovies(movies, movieId, 12);
  return {
    ...movie,
    cast: "",
    director: "",
    runtime: null,
    vote_average: (movie as any).vote_average ?? null,
    similar_movies: similar
  };
};

export const fetchSimilarMovies = async (movieId: number, method: string, topK = 12) => {
  if (API_MODE === "backend") {
    const { data } = await api.get<{ items: MovieCard[] }>(`/movies/${movieId}/similar`, {
      params: { method, top_k: topK }
    });
    return normalizeMovieList(data.items || []).slice(0, topK);
  }
  const recCache = await readStaticJson<RecoCache>("recommendations_cache.json");
  const byMovie = recCache.similar_by_movie?.[String(movieId)]?.[method];
  if (Array.isArray(byMovie) && byMovie.length) return normalizeMovieList(byMovie).slice(0, topK);
  const movies = await readStaticJson<MovieCard[]>("movies.json");
  return similarFromMovies(normalizeMovieList(movies), movieId, topK);
};

export const fetchDiscover = async (params: {
  genres?: string;
  keywords?: string;
  year_min?: number;
  year_max?: number;
  top_k?: number;
}) => {
  if (API_MODE === "backend") {
    const { data } = await api.get<{ items: MovieCard[] }>("/discover", { params });
    return normalizeMovieList(data.items || []);
  }
  const movies = normalizeMovieList(await readStaticJson<MovieCard[]>("movies.json"));
  const genres = (params.genres || "")
    .split(",")
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean);
  const keywords = (params.keywords || "")
    .split(",")
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean);
  const topK = params.top_k || 12;
  return movies
    .filter((m) => {
      const gHit = !genres.length || genres.some((g) => (m.genres || "").toLowerCase().includes(g));
      const kHit =
        !keywords.length ||
        keywords.some((k) => (m.overview || "").toLowerCase().includes(k) || (m.title || "").toLowerCase().includes(k));
      const y = m.year || 0;
      const yMinOk = params.year_min == null || y >= params.year_min;
      const yMaxOk = params.year_max == null || y <= params.year_max;
      return gHit && kHit && yMinOk && yMaxOk;
    })
    .slice(0, topK);
};

export const fetchSearch = async (q: string, topK = 20) => {
  if (API_MODE === "backend") {
    const { data } = await api.get<{ items: MovieCard[] }>("/search", { params: { q, top_k: topK } });
    return normalizeMovieList(data.items || []);
  }
  const index = normalizeMovieList(await readStaticJson<MovieCard[]>("search_index.json"));
  const needle = q.trim().toLowerCase();
  if (!needle) return [];
  return index.filter((m) => (m.title || "").toLowerCase().includes(needle)).slice(0, topK);
};

export const fetchEvaluation = async () => {
  if (API_MODE === "backend") {
    const { data } = await api.get<{ items: EvaluationRow[] }>("/evaluation");
    return data.items || [];
  }
  return await readStaticJson<EvaluationRow[]>("evaluation_results.json");
};

export const fetchAlgorithmLab = async (params: Record<string, string | number>) => {
  if (API_MODE === "backend") {
    const { data } = await api.get("/algorithm-lab", { params });
    return data;
  }
  const userId = Number(params.user_id || 1);
  const topK = Number(params.top_k || 12);
  const [popularity, usercf, itemcf, mf, content, hybrid] = await Promise.all([
    fetchRecommend(userId, "popularity", topK),
    fetchRecommend(userId, "usercf", topK),
    fetchRecommend(userId, "itemcf", topK),
    fetchRecommend(userId, "mf", topK),
    fetchRecommend(userId, "content", topK),
    fetchRecommend(userId, "hybrid", topK)
  ]);
  return {
    user_id: userId,
    top_k: topK,
    results: { popularity, usercf, itemcf, mf, content, hybrid }
  };
};

