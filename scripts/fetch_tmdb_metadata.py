from __future__ import annotations

import argparse
import os
import random
import time
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv

from src.utils.io import ensure_dir, read_json, write_json
from src.utils.logger import get_logger

logger = get_logger("fetch_tmdb_metadata")


def _safe_int(value: Any) -> int | None:
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return int(value)
    except Exception:
        return None


def _needs_enrich(row: pd.Series) -> bool:
    poster_path = str(row.get("poster_path") or "").strip()
    backdrop_path = str(row.get("backdrop_path") or "").strip()
    overview = str(row.get("overview") or "").strip()
    return (not poster_path) or (not backdrop_path) or (not overview)


def _call_tmdb_movie(
    tmdb_id: int,
    token: str,
    api_base: str,
    max_retries: int = 3,
) -> dict | None:
    url = f"{api_base.rstrip('/')}/movie/{tmdb_id}"
    headers = {"accept": "application/json", "Authorization": f"Bearer {token}"}
    params = {"language": "en-US"}
    backoff = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(url, headers=headers, params=params, timeout=15.0)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = backoff + random.uniform(0.3, 1.2)
                logger.warning("TMDB 429 for tmdbId=%s, sleeping %.2fs", tmdb_id, wait)
                time.sleep(wait)
                backoff *= 2
                continue
            if 500 <= resp.status_code < 600:
                wait = backoff + random.uniform(0.1, 0.4)
                logger.warning("TMDB %s for tmdbId=%s, retrying in %.2fs", resp.status_code, tmdb_id, wait)
                time.sleep(wait)
                backoff *= 2
                continue
            logger.warning("TMDB non-retriable status=%s for tmdbId=%s", resp.status_code, tmdb_id)
            return None
        except Exception as exc:
            if attempt == max_retries:
                logger.warning("TMDB request failed for tmdbId=%s: %s", tmdb_id, exc)
                return None
            wait = backoff + random.uniform(0.1, 0.4)
            time.sleep(wait)
            backoff *= 2
    return None


def run(
    input_csv: str,
    output_csv: str,
    cache_json: str,
    limit: int = 1000,
    force: bool = False,
) -> None:
    load_dotenv()
    token = os.getenv("TMDB_READ_ACCESS_TOKEN", "").strip()
    api_base = os.getenv("TMDB_API_BASE", "https://api.themoviedb.org/3").strip()
    image_base = os.getenv("TMDB_IMAGE_BASE", "https://image.tmdb.org/t/p").strip().rstrip("/")
    poster_size = os.getenv("TMDB_POSTER_SIZE", "w500").strip()
    backdrop_size = os.getenv("TMDB_BACKDROP_SIZE", "original").strip()

    df = pd.read_csv(input_csv)
    for col in ["poster_path", "backdrop_path", "overview", "poster_url", "backdrop_url"]:
        if col not in df.columns:
            df[col] = ""

    cache_path = Path(cache_json)
    ensure_dir(cache_path.parent)
    cache = read_json(cache_path) if cache_path.exists() else {}
    if not isinstance(cache, dict):
        cache = {}

    candidates = df[df["tmdbId"].notna()].copy()
    candidates = candidates[candidates.apply(_needs_enrich, axis=1)]
    if limit > 0:
        candidates = candidates.head(limit)

    if not token:
        logger.warning("TMDB_READ_ACCESS_TOKEN not set. Skipping TMDB API enrichment.")
        df.to_csv(output_csv, index=False)
        write_json(cache_path, cache)
        return

    updated = 0
    for idx, row in candidates.iterrows():
        tmdb_id = _safe_int(row.get("tmdbId"))
        if tmdb_id is None:
            continue
        key = str(tmdb_id)
        payload = None
        if not force:
            payload = cache.get(key)

        if payload is None:
            payload = _call_tmdb_movie(tmdb_id=tmdb_id, token=token, api_base=api_base, max_retries=3)
            time.sleep(random.uniform(0.05, 0.2))
            if payload is None:
                continue
            cache[key] = payload

        poster_path = payload.get("poster_path") if isinstance(payload, dict) else None
        backdrop_path = payload.get("backdrop_path") if isinstance(payload, dict) else None
        overview = payload.get("overview") if isinstance(payload, dict) else None
        release_date = payload.get("release_date") if isinstance(payload, dict) else None
        runtime = payload.get("runtime") if isinstance(payload, dict) else None
        vote_average = payload.get("vote_average") if isinstance(payload, dict) else None
        vote_count = payload.get("vote_count") if isinstance(payload, dict) else None
        popularity = payload.get("popularity") if isinstance(payload, dict) else None
        genres = payload.get("genres") if isinstance(payload, dict) else None

        if poster_path:
            df.at[idx, "poster_path"] = poster_path
            df.at[idx, "poster_url"] = f"{image_base}/{poster_size}{poster_path}"
        if backdrop_path:
            df.at[idx, "backdrop_path"] = backdrop_path
            df.at[idx, "backdrop_url"] = f"{image_base}/{backdrop_size}{backdrop_path}"
        if overview:
            df.at[idx, "overview"] = overview
        if release_date:
            df.at[idx, "release_date"] = release_date
        if runtime is not None:
            df.at[idx, "runtime"] = runtime
        if vote_average is not None:
            df.at[idx, "vote_average"] = vote_average
        if vote_count is not None:
            df.at[idx, "vote_count"] = vote_count
        if popularity is not None:
            df.at[idx, "popularity"] = popularity
        if genres is not None:
            df.at[idx, "tmdb_genres"] = str(genres)
        updated += 1

    df.to_csv(output_csv, index=False)
    write_json(cache_path, cache)
    logger.info("TMDB enrichment finished. updated=%s output=%s", updated, output_csv)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch TMDB metadata into processed movie csv")
    parser.add_argument("--input", default="data/processed/movies_enriched.csv")
    parser.add_argument("--output", default="data/processed/movies_enriched_with_tmdb.csv")
    parser.add_argument("--cache", default="data/processed/tmdb_cache.json")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run(
        input_csv=args.input,
        output_csv=args.output,
        cache_json=args.cache,
        limit=args.limit,
        force=args.force,
    )


if __name__ == "__main__":
    main()

