import { MovieCard } from "../types";

const PUBLIC_BASE = import.meta.env.BASE_URL || "/";

export const PLACEHOLDER_POSTER = `${PUBLIC_BASE.replace(/\/$/, "")}/placeholder-poster.png`;

function isHttpUrl(value: string): boolean {
  return value.startsWith("http://") || value.startsWith("https://");
}

function isTmdbImageCdn(value: string): boolean {
  return value.startsWith("https://image.tmdb.org/");
}

function looksLikeBrokenTmdbPoster(url: string): boolean {
  // Broken samples look like: https://image.tmdb.org/t/p/w500Midnight Man
  return url.includes("image.tmdb.org/t/p/w500") && !url.includes("/w500/");
}

function looksLikeBrokenTmdbBackdrop(url: string): boolean {
  return url.includes("image.tmdb.org/t/p/original") && !url.includes("/original/");
}

export function sanitizePosterUrl(url?: string | null): string {
  if (!url || typeof url !== "string") return PLACEHOLDER_POSTER;
  const trimmed = url.trim();
  if (!trimmed) return PLACEHOLDER_POSTER;
  if (trimmed === "/placeholder-poster.png" || trimmed.endsWith("/placeholder-poster.png")) return PLACEHOLDER_POSTER;
  if (trimmed.includes("api.themoviedb.org")) return PLACEHOLDER_POSTER;
  if (looksLikeBrokenTmdbPoster(trimmed)) return PLACEHOLDER_POSTER;
  if (trimmed.startsWith("/")) return trimmed;
  if (!isHttpUrl(trimmed)) return PLACEHOLDER_POSTER;
  if (!isTmdbImageCdn(trimmed)) return PLACEHOLDER_POSTER;
  return trimmed;
}

export function sanitizeBackdropUrl(url?: string | null): string | undefined {
  if (!url || typeof url !== "string") return undefined;
  const trimmed = url.trim();
  if (!trimmed) return undefined;
  if (trimmed.includes("api.themoviedb.org")) return undefined;
  if (looksLikeBrokenTmdbBackdrop(trimmed)) return undefined;
  if (trimmed.startsWith("/")) return trimmed;
  if (!isHttpUrl(trimmed)) return undefined;
  if (!isTmdbImageCdn(trimmed)) return undefined;
  return trimmed;
}

export function sanitizeTitle(title?: string | null): string {
  if (!title || typeof title !== "string") return "";
  const t = title.trim();
  if (!t) return "";
  if (t.toLowerCase() === "unknown movie") return "";
  return t;
}

export function isDisplayableMovie(movie?: Partial<MovieCard> | null): movie is MovieCard {
  if (!movie) return false;
  const id = Number(movie.movieId || 0);
  if (!Number.isFinite(id) || id <= 0) return false;
  return Boolean(sanitizeTitle(movie.title));
}
