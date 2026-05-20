import { MovieCard } from "../types";

const KEYS = {
  liked: "liked_movies",
  disliked: "disliked_movies",
  watchlist: "watchlist"
} as const;

type LibraryKey = keyof typeof KEYS;

function canUseStorage() {
  return typeof window !== "undefined" && Boolean(window.localStorage);
}

function read(key: LibraryKey): MovieCard[] {
  if (!canUseStorage()) return [];
  try {
    const raw = window.localStorage.getItem(KEYS[key]);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(key: LibraryKey, movies: MovieCard[]) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(KEYS[key], JSON.stringify(movies));
  window.dispatchEvent(new CustomEvent("moviemate-library-change", { detail: { key } }));
}

function compactMovie(movie: MovieCard): MovieCard {
  return {
    movieId: movie.movieId,
    title: movie.title,
    year: movie.year,
    genres: movie.genres,
    poster_url: movie.poster_url,
    backdrop_url: movie.backdrop_url,
    overview: movie.overview,
    score: movie.score,
    reason: movie.reason,
    rating_avg: movie.rating_avg,
    rating_count: movie.rating_count,
    reason_type: movie.reason_type,
    evidence: movie.evidence,
    score_breakdown: movie.score_breakdown,
    review_snippet: movie.review_snippet,
    reviews: movie.reviews,
    highlight: movie.highlight,
    source_movie: movie.source_movie
  };
}

export function getLibraryMovies(key: LibraryKey) {
  return read(key);
}

export function hasMovie(key: LibraryKey, movieId: number) {
  return read(key).some((movie) => Number(movie.movieId) === Number(movieId));
}

export function addMovie(key: LibraryKey, movie: MovieCard) {
  const movies = read(key).filter((item) => Number(item.movieId) !== Number(movie.movieId));
  write(key, [compactMovie(movie), ...movies].slice(0, 200));
}

export function removeMovie(key: LibraryKey, movieId: number) {
  write(key, read(key).filter((movie) => Number(movie.movieId) !== Number(movieId)));
}

export function toggleMovie(key: LibraryKey, movie: MovieCard) {
  if (hasMovie(key, movie.movieId)) {
    removeMovie(key, movie.movieId);
    return false;
  }
  addMovie(key, movie);
  return true;
}

export function getMovieState(movieId: number) {
  return {
    liked: hasMovie("liked", movieId),
    disliked: hasMovie("disliked", movieId),
    watchlisted: hasMovie("watchlist", movieId)
  };
}

export function onLibraryChange(callback: () => void) {
  if (!canUseStorage()) return () => undefined;
  const handler = () => callback();
  window.addEventListener("storage", handler);
  window.addEventListener("moviemate-library-change", handler as EventListener);
  return () => {
    window.removeEventListener("storage", handler);
    window.removeEventListener("moviemate-library-change", handler as EventListener);
  };
}
