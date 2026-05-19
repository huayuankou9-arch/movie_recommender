from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.io import read_yaml


class MovieService:
    _instance = None

    def __init__(self):
        cfg = read_yaml("config.yaml")
        processed_dir = Path(cfg["data"]["processed_dir"])
        with_tmdb = processed_dir / "movies_enriched_with_tmdb.csv"
        source = with_tmdb if with_tmdb.exists() else (processed_dir / "movies_enriched.csv")
        self.movies_df = pd.read_csv(source)
        self.default_poster = "/placeholder-poster.png"

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _safe_poster(self, value) -> str:
        if isinstance(value, str) and value.strip():
            return value
        return self.default_poster

    def _safe_backdrop(self, value):
        if isinstance(value, str) and value.strip():
            return value
        return None

    def get_movie(self, movie_id: int) -> dict | None:
        row = self.movies_df[self.movies_df["movieId"] == movie_id]
        if row.empty:
            return None
        r = row.iloc[0]
        return {
            "movieId": int(r.movieId),
            "tmdbId": int(r.tmdbId) if pd.notna(r.tmdbId) else None,
            "imdbId": int(r.imdbId) if pd.notna(r.imdbId) else None,
            "title": r.title if pd.notna(r.title) else "Unknown Movie",
            "year": int(r.year) if pd.notna(r.year) else None,
            "genres": r.genres if pd.notna(r.genres) else "",
            "overview": r.overview if pd.notna(r.overview) else "",
            "keywords": r.keywords if pd.notna(r.keywords) else "",
            "cast": r.cast if pd.notna(r.cast) else "",
            "director": r.director if pd.notna(r.director) else "",
            "poster_url": self._safe_poster(r.poster_url),
            "backdrop_url": self._safe_backdrop(r.backdrop_url),
            "release_date": r.release_date if pd.notna(r.release_date) else None,
            "runtime": float(r.runtime) if pd.notna(r.runtime) else None,
            "vote_average": float(r.vote_average) if pd.notna(r.vote_average) else None,
            "vote_count": float(r.vote_count) if pd.notna(r.vote_count) else None,
            "popularity": float(r.popularity) if pd.notna(r.popularity) else None,
        }

    def search(self, q: str, top_k: int = 20) -> list[dict]:
        q = q.strip().lower()
        if not q:
            return []
        df = self.movies_df[
            self.movies_df["title"].fillna("").str.lower().str.contains(q, regex=False)
            | self.movies_df["clean_title"].fillna("").str.contains(q, regex=False)
        ].head(top_k)
        return [
            {
                "movieId": int(r.movieId),
                "title": r.title if pd.notna(r.title) else "Unknown Movie",
                "year": int(r.year) if pd.notna(r.year) else None,
                "genres": r.genres if pd.notna(r.genres) else "",
                "poster_url": self._safe_poster(r.poster_url),
                "overview": r.overview if pd.notna(r.overview) else "",
            }
            for r in df.itertuples(index=False)
        ]

