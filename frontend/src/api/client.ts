import axios from "axios";
import { EvaluationRow, HomeResponse, MovieCard, UserProfile } from "../types";

const apiBase = import.meta.env.VITE_API_BASE || "/api";

export const api = axios.create({
  baseURL: apiBase,
  timeout: 20000
});

export const fetchHome = async (userId: number) => {
  const { data } = await api.get<HomeResponse>("/home", { params: { user_id: userId } });
  return data;
};

export const fetchRecommend = async (userId: number, model: string, topK = 12) => {
  const { data } = await api.get<{ items: MovieCard[] }>(`/recommend/${userId}`, {
    params: { model, top_k: topK }
  });
  return data.items;
};

export const fetchProfile = async (userId: number) => {
  const { data } = await api.get<UserProfile>(`/users/${userId}/profile`);
  return data;
};

export const fetchMovieDetail = async (movieId: number) => {
  const { data } = await api.get(`/movies/${movieId}`);
  return data;
};

export const fetchSimilarMovies = async (movieId: number, method: string, topK = 12) => {
  const { data } = await api.get<{ items: MovieCard[] }>(`/movies/${movieId}/similar`, {
    params: { method, top_k: topK }
  });
  return data.items;
};

export const fetchDiscover = async (params: {
  genres?: string;
  keywords?: string;
  year_min?: number;
  year_max?: number;
  top_k?: number;
}) => {
  const { data } = await api.get<{ items: MovieCard[] }>("/discover", { params });
  return data.items;
};

export const fetchSearch = async (q: string, topK = 20) => {
  const { data } = await api.get<{ items: MovieCard[] }>("/search", { params: { q, top_k: topK } });
  return data.items;
};

export const fetchEvaluation = async () => {
  const { data } = await api.get<{ items: EvaluationRow[] }>("/evaluation");
  return data.items;
};

export const fetchAlgorithmLab = async (params: Record<string, string | number>) => {
  const { data } = await api.get("/algorithm-lab", { params });
  return data;
};

export const repairPoster = async (movieId: number, currentUrl?: string) => {
  const { data } = await api.post(`/movies/${movieId}/poster/repair`, null, {
    params: { current_url: currentUrl }
  });
  return data as { poster_url?: string; backdrop_url?: string; source?: string };
};
