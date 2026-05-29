export interface MovieCard {
  movieId: number;
  title: string;
  year?: number | null;
  genres?: string;
  poster_url?: string;
  backdrop_url?: string;
  overview?: string;
  score?: number;
  reason?: string;
  rating_avg?: number | null;
  rating_count?: number | null;
  review_snippet?: string;
  reviews?: Array<{ text: string; rating?: number | null; userId?: number | null }>;
  reason_type?: string;
  evidence?: string;
  score_breakdown?: Record<string, number | null | undefined> & {
    recommendation?: number | null;
    rating_avg?: number | null;
    rating_count?: number | null;
    popularity?: number | null;
    mf?: number | null;
    itemcf?: number | null;
    content?: number | null;
    usercf?: number | null;
  };
  source_movie?: Partial<MovieCard> | null;
  user_rating?: number | null;
  highlight?: string;
}

export interface GenreRow {
  genre: string;
  movies: MovieCard[];
}

export interface HomeResponse {
  hero_movie: MovieCard | null;
  for_you: MovieCard[];
  trending: MovieCard[];
  highly_rated: MovieCard[];
  because_you_like: MovieCard[];
  genre_rows: GenreRow[];
}

export interface UserProfile {
  userId: number;
  rating_count: number;
  avg_rating: number;
  favorite_genres: string[];
  genre_distribution: { genre: string; count: number }[];
  top_rated_movies: Array<MovieCard & { rating: number }>;
  recent_movies: Array<MovieCard & { rating: number }>;
  profile_summary: string;
}

export interface EvaluationRow {
  model: string;
  rmse?: number | null;
  mae?: number | null;
  "precision@10": number;
  "recall@10": number;
  "hitrate@10": number;
  "ndcg@10": number;
  coverage: number;
}

export interface EvaluationPayload {
  full_ranking: EvaluationRow[];
  sampled_ranking: EvaluationRow[];
  rating_prediction: Array<{ model: string; rmse?: number | null; mae?: number | null }>;
  best_hybrid_weights?: Record<string, number>;
  notes?: Record<string, string>;
}

export interface BuildInfo {
  generated_at: string;
  dataset: string;
  movies_cached: number;
  users_cached: number;
  tmdb_enriched: number;
}
