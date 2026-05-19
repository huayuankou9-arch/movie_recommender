from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv

from src.utils.io import ensure_dir, read_json, read_yaml, write_json


class MovieService:
    _instance = None

    def __init__(self):
        load_dotenv()
        cfg = read_yaml("config.yaml")
        processed_dir = Path(cfg["data"]["processed_dir"])
        self.movies_df = pd.read_csv(processed_dir / "movies_enriched.csv")
        self.cfg = cfg
        self.movie_map = self.movies_df.set_index("movieId").to_dict("index")
        self.default_poster = cfg.get("app", {}).get("default_poster", "https://placehold.co/500x750?text=No+Poster")
        self.default_backdrop = cfg.get("app", {}).get(
            "default_backdrop", "https://placehold.co/1200x675?text=No+Backdrop"
        )
        self.cache_path = Path(cfg["data"]["output_dir"]) / "cache" / "poster_repair_cache.json"
        ensure_dir(self.cache_path.parent)
        self._cache_lock = threading.Lock()
        self._cache = self._load_cache()
        self.tmdb_api_key = os.getenv("TMDB_API_KEY", "").strip()
        self.tmdb_read_token = os.getenv("TMDB_API_READ_TOKEN", "").strip()
        self.tmdb_base = "https://api.themoviedb.org/3"

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_cache(self) -> dict:
        if self.cache_path.exists():
            try:
                data = read_json(self.cache_path)
                if isinstance(data, dict):
                    data.setdefault("movies", {})
                    data.setdefault("url_status", {})
                    return data
            except Exception:
                pass
        return {"movies": {}, "url_status": {}}

    def _save_cache(self) -> None:
        with self._cache_lock:
            write_json(self.cache_path, self._cache)

    def _headers(self) -> dict:
        headers = {"accept": "application/json"}
        if self.tmdb_read_token:
            headers["Authorization"] = f"Bearer {self.tmdb_read_token}"
        return headers

    def _has_tmdb_auth(self) -> bool:
        return bool(self.tmdb_api_key or self.tmdb_read_token)

    def _validate_image_url(self, url: str | None, timeout: float = 8.0) -> bool:
        if not isinstance(url, str) or not url.strip():
            return False
        if "placehold.co" in url:
            return True
        cached = self._cache["url_status"].get(url)
        if cached == "ok":
            return True
        if cached == "broken":
            return False
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            ok = resp.status_code == 200 and str(resp.headers.get("content-type", "")).startswith("image/")
            self._cache["url_status"][url] = "ok" if ok else "broken"
            return ok
        except Exception:
            self._cache["url_status"][url] = "broken"
            return False

    def _tmdb_details(self, tmdb_id: int) -> dict | None:
        url = f"{self.tmdb_base}/movie/{tmdb_id}"
        params = {"language": "en-US"}
        if self.tmdb_api_key:
            params["api_key"] = self.tmdb_api_key
        try:
            resp = httpx.get(url, headers=self._headers(), params=params, timeout=12.0)
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    def repair_poster(self, movie_id: int, current_url: str | None = None, force: bool = False) -> dict:
        mid = int(movie_id)
        row = self.movie_map.get(mid, {})
        fallback = {
            "movieId": mid,
            "title": row.get("title") or "Unknown Movie",
            "poster_url": self.default_poster,
            "backdrop_url": self.default_backdrop,
            "source": "fallback",
        }
        if not row:
            return fallback

        mid_key = str(mid)
        cached_movie = self._cache["movies"].get(mid_key, {})
        if cached_movie and not force:
            poster_url = cached_movie.get("poster_url")
            backdrop_url = cached_movie.get("backdrop_url") or self.default_backdrop
            if self._validate_image_url(poster_url):
                return {
                    "movieId": mid,
                    "title": row.get("title") or "Unknown Movie",
                    "poster_url": poster_url,
                    "backdrop_url": backdrop_url,
                    "source": cached_movie.get("source", "cache"),
                }

        candidates = [current_url, row.get("poster_url")]
        for c in candidates:
            if self._validate_image_url(c):
                payload = {
                    "poster_url": c,
                    "backdrop_url": row.get("backdrop_url") or self.default_backdrop,
                    "source": "original",
                    "updated_at": datetime.utcnow().isoformat(),
                }
                self._cache["movies"][mid_key] = payload
                self._save_cache()
                return {
                    "movieId": mid,
                    "title": row.get("title") or "Unknown Movie",
                    **payload,
                }

        if self._has_tmdb_auth():
            tmdb_id = row.get("tmdbId")
            if tmdb_id is not None and not pd.isna(tmdb_id):
                details = self._tmdb_details(int(tmdb_id))
                if details:
                    poster_path = details.get("poster_path")
                    backdrop_path = details.get("backdrop_path")
                    poster_url = (
                        f"https://image.tmdb.org/t/p/w500{poster_path}"
                        if isinstance(poster_path, str) and poster_path.startswith("/")
                        else self.default_poster
                    )
                    backdrop_url = (
                        f"https://image.tmdb.org/t/p/original{backdrop_path}"
                        if isinstance(backdrop_path, str) and backdrop_path.startswith("/")
                        else self.default_backdrop
                    )
                    if self._validate_image_url(poster_url):
                        payload = {
                            "poster_url": poster_url,
                            "backdrop_url": backdrop_url,
                            "source": "tmdb_api",
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                        self._cache["movies"][mid_key] = payload
                        self._save_cache()
                        self.movies_df.loc[self.movies_df["movieId"] == mid, "poster_url"] = poster_url
                        self.movies_df.loc[self.movies_df["movieId"] == mid, "backdrop_url"] = backdrop_url
                        self.movie_map[mid]["poster_url"] = poster_url
                        self.movie_map[mid]["backdrop_url"] = backdrop_url
                        return {
                            "movieId": mid,
                            "title": row.get("title") or "Unknown Movie",
                            **payload,
                        }

        payload = {
            "poster_url": self.default_poster,
            "backdrop_url": row.get("backdrop_url") or self.default_backdrop,
            "source": "fallback",
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._cache["movies"][mid_key] = payload
        self._save_cache()
        return {"movieId": mid, "title": row.get("title") or "Unknown Movie", **payload}

    def get_movie(self, movie_id: int) -> dict | None:
        row = self.movies_df[self.movies_df["movieId"] == movie_id]
        if row.empty:
            return None
        r = row.iloc[0]
        cached = self._cache.get("movies", {}).get(str(int(movie_id)), {})
        poster_url = cached.get("poster_url") or r.poster_url
        backdrop_url = cached.get("backdrop_url") or r.backdrop_url
        return {
            "movieId": int(r.movieId),
            "tmdbId": int(r.tmdbId) if pd.notna(r.tmdbId) else None,
            "imdbId": int(r.imdbId) if pd.notna(r.imdbId) else None,
            "title": r.title,
            "year": int(r.year) if pd.notna(r.year) else None,
            "genres": r.genres,
            "overview": r.overview,
            "keywords": r.keywords,
            "cast": r.cast,
            "director": r.director,
            "poster_url": poster_url,
            "backdrop_url": backdrop_url,
            "release_date": r.release_date,
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
                "title": r.title,
                "year": int(r.year) if pd.notna(r.year) else None,
                "genres": r.genres,
                "poster_url": self._cache.get("movies", {}).get(str(int(r.movieId)), {}).get("poster_url") or r.poster_url,
                "overview": r.overview,
            }
            for r in df.itertuples(index=False)
        ]
