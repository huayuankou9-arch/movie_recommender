from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.io import ensure_dir, read_json, write_json
from src.utils.logger import get_logger

logger = get_logger("export_static_data")

PLACEHOLDER_POSTER = "/placeholder-poster.png"


def _clean_movie_row(row: pd.Series) -> dict[str, Any]:
    poster_url = row.get("poster_url")
    backdrop_url = row.get("backdrop_url")
    if not isinstance(poster_url, str) or not poster_url.strip():
        poster_url = PLACEHOLDER_POSTER
    if isinstance(backdrop_url, str) and not backdrop_url.strip():
        backdrop_url = None
    return {
        "movieId": int(row["movieId"]),
        "tmdbId": int(row["tmdbId"]) if pd.notna(row.get("tmdbId")) else None,
        "title": str(row.get("title") or "Unknown Movie"),
        "year": int(row["year"]) if pd.notna(row.get("year")) else None,
        "genres": str(row.get("genres") or ""),
        "overview": str(row.get("overview") or ""),
        "poster_url": poster_url,
        "backdrop_url": backdrop_url,
        "vote_average": float(row["vote_average"]) if pd.notna(row.get("vote_average")) else None,
        "vote_count": int(row["vote_count"]) if pd.notna(row.get("vote_count")) else None,
        "popularity": float(row["popularity"]) if pd.notna(row.get("popularity")) else None,
        "reason": "",
    }


def _load_json_or_default(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return read_json(path)
    except Exception:
        return default


def run(
    movies_csv: str,
    recommendations_cache_json: str,
    evaluation_csv: str,
    out_dir: str,
) -> None:
    out_path = ensure_dir(out_dir)
    movies_df = pd.read_csv(movies_csv)
    movies = [_clean_movie_row(row) for _, row in movies_df.iterrows()]
    movie_by_id = {m["movieId"]: m for m in movies}

    rec_cache_path = Path(recommendations_cache_json)
    rec_cache = _load_json_or_default(rec_cache_path, default={})
    if not isinstance(rec_cache, dict):
        rec_cache = {}

    home_cache = rec_cache.get("home_cache", {})
    if not home_cache:
        fallback_home = _load_json_or_default(Path("data/outputs/cache/home_cache.json"), default={})
        if isinstance(fallback_home, dict):
            home_cache = fallback_home

    eval_df = pd.read_csv(evaluation_csv) if Path(evaluation_csv).exists() else pd.DataFrame()
    eval_items = eval_df.to_dict(orient="records") if not eval_df.empty else []

    search_index = [
        {
            "movieId": m["movieId"],
            "title": m["title"],
            "year": m["year"],
            "genres": m["genres"],
            "poster_url": m["poster_url"] or PLACEHOLDER_POSTER,
        }
        for m in movies
    ]

    # Normalize recommendation payloads and guarantee poster fallback.
    def _normalize_items(items: list[dict]) -> list[dict]:
        out = []
        for it in items or []:
            mid = int(it.get("movieId"))
            base = movie_by_id.get(mid, {})
            poster_url = it.get("poster_url") or base.get("poster_url") or PLACEHOLDER_POSTER
            if not isinstance(poster_url, str) or not poster_url.strip():
                poster_url = PLACEHOLDER_POSTER
            backdrop_url = it.get("backdrop_url") or base.get("backdrop_url")
            if isinstance(backdrop_url, str) and not backdrop_url.strip():
                backdrop_url = None
            out.append(
                {
                    "movieId": mid,
                    "tmdbId": base.get("tmdbId"),
                    "title": it.get("title") or base.get("title") or "Unknown Movie",
                    "year": it.get("year") if it.get("year") is not None else base.get("year"),
                    "genres": it.get("genres") or base.get("genres") or "",
                    "overview": it.get("overview") or base.get("overview") or "",
                    "poster_url": poster_url,
                    "backdrop_url": backdrop_url,
                    "vote_average": base.get("vote_average"),
                    "vote_count": base.get("vote_count"),
                    "popularity": base.get("popularity"),
                    "score": it.get("score"),
                    "reason": it.get("reason") or "",
                }
            )
        return out

    for user_id, payload in list(home_cache.items()):
        if not isinstance(payload, dict):
            continue
        if payload.get("hero_movie"):
            payload["hero_movie"] = _normalize_items([payload["hero_movie"]])[0]
        for sec in ["for_you", "trending", "highly_rated", "because_you_like"]:
            payload[sec] = _normalize_items(payload.get(sec, []))
        rows = payload.get("genre_rows", [])
        if isinstance(rows, list):
            for row in rows:
                row["movies"] = _normalize_items(row.get("movies", []))

    if "users" in rec_cache and isinstance(rec_cache["users"], dict):
        for _, user_payload in rec_cache["users"].items():
            if not isinstance(user_payload, dict):
                continue
            for k, v in list(user_payload.items()):
                if isinstance(v, list):
                    user_payload[k] = _normalize_items(v)

    write_json(out_path / "movies.json", movies)
    write_json(out_path / "home_cache.json", home_cache)
    write_json(out_path / "recommendations_cache.json", rec_cache)
    write_json(out_path / "evaluation_results.json", eval_items)
    write_json(out_path / "search_index.json", search_index)
    logger.info("Static data exported to %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export static JSON data for frontend")
    parser.add_argument("--movies", default="data/processed/movies_enriched_with_tmdb.csv")
    parser.add_argument("--recommendations", default="data/outputs/cache/recommendations_cache.json")
    parser.add_argument("--evaluation", default="reports/tables/evaluation_results.csv")
    parser.add_argument("--output-dir", default="frontend/public/data")
    args = parser.parse_args()
    run(
        movies_csv=args.movies,
        recommendations_cache_json=args.recommendations,
        evaluation_csv=args.evaluation,
        out_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()

