from __future__ import annotations

import argparse
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv

from src.utils.io import ensure_dir, read_json, write_json
from src.utils.logger import get_logger
from src.utils.text import safe_literal_eval

logger = get_logger("fetch_tmdb_metadata")
_LOCAL_METADATA_CACHE: dict[str, dict] | None = None


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


def _is_missing_text(value: Any) -> bool:
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    text = str(value or "").strip()
    return not text or text.lower() in {"nan", "none", "null"}


def _looks_like_tmdb_image(url: str) -> bool:
    return url.startswith("https://image.tmdb.org/t/p/")


def _looks_malformed_poster(url: str) -> bool:
    if not url:
        return True
    if "api.themoviedb.org" in url:
        return True
    if "image.tmdb.org/t/p/w500" in url and "/w500/" not in url:
        return True
    return not _looks_like_tmdb_image(url)


def _poster_url_ok(url: str, timeout: float = 12.0) -> bool:
    if _looks_malformed_poster(url):
        return False
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.head(url)
            if resp.status_code == 405:
                resp = client.get(url, headers={"Range": "bytes=0-0"})
            return 200 <= resp.status_code < 400
    except Exception:
        return False


def _find_bad_poster_movie_ids(df: pd.DataFrame, max_workers: int = 24) -> set[int]:
    candidates: list[tuple[int, str]] = []
    missing: set[int] = set()
    for row in df.itertuples(index=False):
        movie_id = _safe_int(getattr(row, "movieId", None))
        if movie_id is None:
            continue
        url = str(getattr(row, "poster_url", "") or "").strip()
        if _looks_malformed_poster(url):
            missing.add(movie_id)
        elif _looks_like_tmdb_image(url):
            candidates.append((movie_id, url))

    bad = set(missing)
    if not candidates:
        return bad
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_poster_url_ok, url): movie_id for movie_id, url in candidates}
        for fut in as_completed(futures):
            movie_id = futures[fut]
            try:
                if not fut.result():
                    bad.add(movie_id)
            except Exception:
                bad.add(movie_id)
    return bad


def _backfill_missing_tmdb_ids(df: pd.DataFrame) -> pd.DataFrame:
    links_paths = [
        Path("data/raw/the-movie-dataset/links_small.csv"),
        Path("data/raw/the-movies-dataset/links_small.csv"),
        Path("data/raw/ml-latest/ml-latest/links.csv"),
        Path("data/raw/ml-latest/links.csv"),
    ]
    for path in links_paths:
        if not path.exists():
            continue
        try:
            links = pd.read_csv(path, usecols=["movieId", "tmdbId"])
        except Exception:
            continue
        links["movieId"] = pd.to_numeric(links["movieId"], errors="coerce").astype("Int64")
        links["tmdbId_fill"] = pd.to_numeric(links["tmdbId"], errors="coerce").astype("Int64")
        before = int(df["tmdbId"].notna().sum())
        df = df.merge(links[["movieId", "tmdbId_fill"]].dropna().drop_duplicates("movieId"), on="movieId", how="left")
        df["tmdbId"] = df["tmdbId"].fillna(df["tmdbId_fill"])
        df = df.drop(columns=["tmdbId_fill"])
        after = int(df["tmdbId"].notna().sum())
        if after > before:
            logger.info("Backfilled %s missing tmdbId values from %s", after - before, path)
    return df


def _local_tmdb_payload(tmdb_id: int) -> dict | None:
    global _LOCAL_METADATA_CACHE
    if _LOCAL_METADATA_CACHE is None:
        _LOCAL_METADATA_CACHE = {}
        paths = [
            Path("data/raw/the-movie-dataset/movies_metadata.csv"),
            Path("data/raw/the-movies-dataset/movies_metadata.csv"),
        ]
        path = next((p for p in paths if p.exists()), None)
        if path is None:
            return None
        try:
            available_cols = pd.read_csv(path, nrows=0).columns.tolist()
            desired_cols = [
                "id",
                "title",
                "overview",
                "poster_path",
                "backdrop_path",
                "release_date",
                "runtime",
                "vote_average",
                "vote_count",
                "popularity",
                "genres",
            ]
            meta = pd.read_csv(
                path,
                usecols=[c for c in desired_cols if c in available_cols],
                low_memory=False,
            )
        except Exception as exc:
            logger.warning("Failed to read local TMDB metadata fallback: %s", exc)
            return None
        meta["id_num"] = pd.to_numeric(meta["id"], errors="coerce").astype("Int64")
        for row in meta.dropna(subset=["id_num"]).itertuples(index=False):
            parsed = safe_literal_eval(getattr(row, "genres", ""), fallback=[])
            genres = [x for x in parsed if isinstance(x, dict)] if isinstance(parsed, list) else []
            _LOCAL_METADATA_CACHE[str(int(row.id_num))] = {
                "title": getattr(row, "title", None),
                "overview": getattr(row, "overview", None),
                "poster_path": getattr(row, "poster_path", None),
                "backdrop_path": getattr(row, "backdrop_path", None) if hasattr(row, "backdrop_path") else None,
                "release_date": getattr(row, "release_date", None),
                "runtime": getattr(row, "runtime", None),
                "vote_average": getattr(row, "vote_average", None),
                "vote_count": getattr(row, "vote_count", None),
                "popularity": getattr(row, "popularity", None),
                "genres": genres,
            }
    return _LOCAL_METADATA_CACHE.get(str(int(tmdb_id)))


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


def _fetch_payloads_concurrently(
    tmdb_ids: list[int],
    token: str,
    api_base: str,
    cache: dict,
    force: bool,
    max_workers: int,
) -> dict[str, dict]:
    unique_ids = sorted({int(x) for x in tmdb_ids if x is not None})
    payloads: dict[str, dict] = {}
    to_fetch: list[int] = []
    for tmdb_id in unique_ids:
        key = str(tmdb_id)
        cached = None if force else cache.get(key)
        if isinstance(cached, dict):
            payloads[key] = cached
        else:
            to_fetch.append(tmdb_id)

    if not to_fetch:
        return payloads

    logger.info("Fetching TMDB metadata concurrently for %s movies", len(to_fetch))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_call_tmdb_movie, tmdb_id=tmdb_id, token=token, api_base=api_base, max_retries=3): tmdb_id
            for tmdb_id in to_fetch
        }
        for idx, fut in enumerate(as_completed(futures), start=1):
            tmdb_id = futures[fut]
            try:
                payload = fut.result()
            except Exception as exc:
                logger.warning("TMDB fetch failed for tmdbId=%s: %s", tmdb_id, exc)
                continue
            if isinstance(payload, dict):
                key = str(tmdb_id)
                cache[key] = payload
                payloads[key] = payload
            if idx % 500 == 0:
                logger.info("Fetched %s/%s TMDB payloads", idx, len(to_fetch))
    return payloads


def run(
    input_csv: str,
    output_csv: str,
    cache_json: str,
    limit: int = 1000,
    force: bool = False,
    movie_ids: list[int] | None = None,
    verify_posters: bool = False,
    verify_workers: int = 24,
    fetch_workers: int = 16,
    batch_size: int = 1000,
) -> None:
    load_dotenv(".env")
    token = (os.getenv("TMDB_READ_ACCESS_TOKEN") or os.getenv("TMDB_API_READ_TOKEN") or "").strip()
    api_base = os.getenv("TMDB_API_BASE", "https://api.themoviedb.org/3").strip()
    image_base = os.getenv("TMDB_IMAGE_BASE", "https://image.tmdb.org/t/p").strip().rstrip("/")
    poster_size = os.getenv("TMDB_POSTER_SIZE", "w500").strip()
    backdrop_size = os.getenv("TMDB_BACKDROP_SIZE", "original").strip()

    df = pd.read_csv(input_csv)
    df = _backfill_missing_tmdb_ids(df)
    for col in ["poster_path", "backdrop_path", "overview", "poster_url", "backdrop_url"]:
        if col not in df.columns:
            df[col] = ""

    cache_path = Path(cache_json)
    ensure_dir(cache_path.parent)
    cache = read_json(cache_path) if cache_path.exists() else {}
    if not isinstance(cache, dict):
        cache = {}

    candidates = df[df["tmdbId"].notna()].copy()
    if movie_ids:
        wanted = {int(x) for x in movie_ids}
        candidates = candidates[candidates["movieId"].apply(lambda x: _safe_int(x) in wanted)]
    elif verify_posters:
        bad_movie_ids = _find_bad_poster_movie_ids(candidates, max_workers=verify_workers)
        candidates = candidates[candidates["movieId"].apply(lambda x: _safe_int(x) in bad_movie_ids)]
    elif not force:
        candidates = candidates[candidates.apply(_needs_enrich, axis=1)]
    if limit > 0:
        candidates = candidates.head(limit)

    if not token:
        logger.warning("TMDB_READ_ACCESS_TOKEN not set. Skipping TMDB API enrichment.")
        df.to_csv(output_csv, index=False)
        write_json(cache_path, cache)
        return

    updated = 0
    rows = list(candidates.iterrows())
    for batch_start in range(0, len(rows), max(1, batch_size)):
        batch = rows[batch_start : batch_start + max(1, batch_size)]
        preloaded_payloads = None
        if verify_posters and not movie_ids:
            tmdb_ids = [_safe_int(row.get("tmdbId")) for _, row in batch]
            preloaded_payloads = _fetch_payloads_concurrently(
                tmdb_ids=[v for v in tmdb_ids if v is not None],
                token=token,
                api_base=api_base,
                cache=cache,
                force=force,
                max_workers=fetch_workers,
            )

        for idx, row in batch:
            tmdb_id = _safe_int(row.get("tmdbId"))
            if tmdb_id is None:
                continue
            key = str(tmdb_id)
            payload = None
            if preloaded_payloads is not None:
                payload = preloaded_payloads.get(key)
            elif not force:
                payload = cache.get(key)

            if payload is None:
                payload = _call_tmdb_movie(tmdb_id=tmdb_id, token=token, api_base=api_base, max_retries=3)
                time.sleep(random.uniform(0.05, 0.2))
                if payload is None:
                    payload = _local_tmdb_payload(tmdb_id)
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
            title = payload.get("title") if isinstance(payload, dict) else None

            if poster_path:
                df.at[idx, "poster_path"] = poster_path
                df.at[idx, "poster_url"] = f"{image_base}/{poster_size}{poster_path}"
            else:
                df.at[idx, "poster_path"] = ""
                df.at[idx, "poster_url"] = ""
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
            if title and str(row.get("title") or "").strip().lower() == "unknown movie":
                df.at[idx, "title"] = title
            updated += 1

        if verify_posters:
            df.to_csv(output_csv, index=False)
            write_json(cache_path, cache)
            logger.info("Persisted TMDB batch %s/%s updated=%s", min(batch_start + batch_size, len(rows)), len(rows), updated)

    if verify_posters:
        logger.info("TMDB enrichment finished. updated=%s output=%s", updated, output_csv)
        return

    for idx, row in rows:
        tmdb_id = _safe_int(row.get("tmdbId"))
        if tmdb_id is None:
            continue
        key = str(tmdb_id)
        payload = None
        if preloaded_payloads is not None:
            payload = preloaded_payloads.get(key)
        elif not force:
            payload = cache.get(key)

        if payload is None:
            payload = _call_tmdb_movie(tmdb_id=tmdb_id, token=token, api_base=api_base, max_retries=3)
            time.sleep(random.uniform(0.05, 0.2))
            if payload is None:
                payload = _local_tmdb_payload(tmdb_id)
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
        title = payload.get("title") if isinstance(payload, dict) else None

        if poster_path:
            df.at[idx, "poster_path"] = poster_path
            df.at[idx, "poster_url"] = f"{image_base}/{poster_size}{poster_path}"
        else:
            df.at[idx, "poster_path"] = ""
            df.at[idx, "poster_url"] = ""
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
        if title and str(row.get("title") or "").strip().lower() == "unknown movie":
            df.at[idx, "title"] = title
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
    parser.add_argument("--movie-ids", default="", help="Comma-separated MovieLens movieId values to refresh")
    parser.add_argument("--verify-posters", action="store_true", help="HEAD-check existing poster URLs and refresh 404s")
    parser.add_argument("--verify-workers", type=int, default=24)
    parser.add_argument("--fetch-workers", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    movie_ids = [int(x.strip()) for x in args.movie_ids.split(",") if x.strip()]
    run(
        input_csv=args.input,
        output_csv=args.output,
        cache_json=args.cache,
        limit=args.limit,
        force=args.force,
        movie_ids=movie_ids,
        verify_posters=args.verify_posters,
        verify_workers=args.verify_workers,
        fetch_workers=args.fetch_workers,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
