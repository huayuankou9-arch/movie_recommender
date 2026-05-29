from __future__ import annotations

import argparse
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.io import ensure_dir, read_json, write_json
from src.utils.logger import get_logger

logger = get_logger("export_static_data")

PLACEHOLDER_POSTER = "/placeholder-poster.png"
ALLOWED_GENRES = {
    "Action",
    "Adventure",
    "Animation",
    "Children",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Fantasy",
    "Film-Noir",
    "Horror",
    "IMAX",
    "Musical",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Thriller",
    "War",
    "Western",
}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _as_str(value: Any, default: str = "") -> str:
    if _is_missing(value):
        return default
    text = str(value).strip()
    if not text:
        return default
    lowered = text.lower()
    if lowered in {"nan", "none", "null"}:
        return default
    return text


def _as_int(value: Any, default: int | None = None) -> int | None:
    if _is_missing(value):
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def _as_float(value: Any, default: float | None = None) -> float | None:
    if _is_missing(value):
        return default
    try:
        out = float(value)
    except Exception:
        return default
    if not math.isfinite(out):
        return default
    return out


def _sanitize_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(v) for v in value]
    if isinstance(value, tuple):
        return [_sanitize_for_json(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if _is_missing(value):
        return None
    return value


def _sanitize_poster_url(value: Any) -> str:
    url = _as_str(value, default="")
    if not url:
        return PLACEHOLDER_POSTER
    if "api.themoviedb.org" in url:
        return PLACEHOLDER_POSTER
    # Broken sample: https://image.tmdb.org/t/p/w500Midnight Man
    if "image.tmdb.org/t/p/w500" in url and "/w500/" not in url:
        return PLACEHOLDER_POSTER
    if url.startswith("/"):
        return url
    if url.startswith("https://image.tmdb.org/"):
        return url
    return PLACEHOLDER_POSTER


def _sanitize_backdrop_url(value: Any) -> str | None:
    url = _as_str(value, default="")
    if not url:
        return None
    if "api.themoviedb.org" in url:
        return None
    if "image.tmdb.org/t/p/original" in url and "/original/" not in url:
        return None
    if url.startswith("/"):
        return url
    if url.startswith("https://image.tmdb.org/"):
        return url
    return None


def _is_unknown_title(value: Any) -> bool:
    title = _as_str(value, default="")
    if not title:
        return True
    return title.strip().lower() == "unknown movie"


def _find_first_existing(paths: list[str]) -> Path | None:
    for path in paths:
        p = Path(path)
        if p.exists():
            return p
    return None


def _movielens_genres_context() -> dict[int, str]:
    path = _find_first_existing(
        [
            "data/raw/ml-latest-small/movies.csv",
            "data/raw/ml-latest/ml-latest/movies.csv",
            "data/raw/ml-latest/movies.csv",
        ]
    )
    if not path:
        return {}
    try:
        df = pd.read_csv(path, usecols=["movieId", "genres"])
    except Exception:
        return {}
    out = {}
    for r in df.itertuples(index=False):
        mid = _as_int(r.movieId, default=None)
        if mid is None:
            continue
        genres = [
            g.strip()
            for g in str(r.genres or "").replace("|", ",").split(",")
            if g.strip() and g.strip() != "(no genres listed)"
        ]
        out[mid] = ", ".join(genres)
    return out


def _clean_genres(value: Any, fallback: str = "") -> str:
    pieces = [g.strip() for g in _as_str(value, default="").split(",") if g.strip()]
    valid = [g for g in pieces if g in ALLOWED_GENRES]
    if valid:
        return ", ".join(dict.fromkeys(valid))
    fallback_pieces = [g.strip() for g in fallback.split(",") if g.strip()]
    fallback_valid = [g for g in fallback_pieces if g in ALLOWED_GENRES]
    return ", ".join(dict.fromkeys(fallback_valid))


def _rating_context(train_path: str, test_path: str) -> dict[int, dict[str, Any]]:
    frames = []
    for path in [train_path, test_path]:
        p = Path(path)
        if p.exists():
            frames.append(pd.read_csv(p, usecols=["movieId", "rating"]))
    if not frames:
        return {}
    ratings = pd.concat(frames, ignore_index=True)
    agg = ratings.groupby("movieId")["rating"].agg(["mean", "count"]).reset_index()
    return {
        int(r.movieId): {
            "rating_avg": round(float(r.mean), 2),
            "rating_count": int(r.count),
        }
        for r in agg.itertuples(index=False)
    }


def _tag_context(tags_path: str | None, movie_ids: set[int], max_tags_per_movie: int = 5) -> dict[int, dict[str, Any]]:
    if not tags_path:
        return {}
    path = Path(tags_path)
    if not path.exists():
        return {}
    tags_by_movie: dict[int, list[str]] = {}
    try:
        chunks = pd.read_csv(path, usecols=["movieId", "tag"], chunksize=200_000)
        for chunk in chunks:
            chunk = chunk[chunk["movieId"].isin(movie_ids)]
            for r in chunk.itertuples(index=False):
                mid = _as_int(r.movieId, default=None)
                tag = _as_str(r.tag, default="")
                if mid is None or not tag:
                    continue
                bucket = tags_by_movie.setdefault(mid, [])
                lowered = {x.lower() for x in bucket}
                if tag.lower() not in lowered and len(bucket) < max_tags_per_movie:
                    bucket.append(tag)
    except Exception as exc:
        logger.warning("Failed to read tags for static export: %s", exc)
        return {}
    out = {}
    for mid, tags in tags_by_movie.items():
        out[mid] = {
            "review_snippet": "User tags: " + " / ".join(tags[:3]) if tags else "",
            "reviews": [{"text": tag} for tag in tags],
        }
    return out


def _reason_payload(item: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    reason = _as_str(item.get("reason"), default="")
    score = _as_float(item.get("score"), default=None)
    title = _as_str(base.get("title"), default="")
    breakdown = item.get("score_breakdown") if isinstance(item.get("score_breakdown"), dict) else {}
    if item.get("reason_type") or item.get("evidence") or breakdown:
        merged = {
            **breakdown,
            "recommendation": score,
            "rating_avg": _as_float(base.get("rating_avg"), default=None),
            "rating_count": _as_int(base.get("rating_count"), default=None),
            "popularity": breakdown.get("popularity", _as_float(base.get("popularity"), default=None)),
        }
        return {
            "reason_type": _as_str(item.get("reason_type"), default="hybrid"),
            "evidence": item.get("evidence") if item.get("evidence") else reason,
            "score_breakdown": merged,
        }
    reason_lower = reason.lower()
    if "similar user" in reason_lower:
        reason_type = "user_similarity"
        evidence = "Similar users also rated it highly."
    elif "because you like" in reason_lower or "because you watched" in reason_lower:
        reason_type = "item_similarity"
        evidence = reason
    elif "content" in reason_lower or "story" in reason_lower:
        reason_type = "content_match"
        evidence = "Genres, tags, and story signals match your profile."
    elif "popular" in reason_lower or "widely watched" in reason_lower:
        reason_type = "popularity"
        evidence = "Many viewers rated this movie highly."
    elif score is not None:
        reason_type = "predicted_rating"
        evidence = f"Predicted recommendation score {score:.2f}."
    else:
        reason_type = "hybrid"
        evidence = f"{title} balances collaborative, content, and popularity signals." if title else reason
    return {
        "reason_type": reason_type,
        "evidence": evidence or reason,
        "score_breakdown": {
            "recommendation": score,
            "rating_avg": _as_float(base.get("rating_avg"), default=None),
            "rating_count": _as_int(base.get("rating_count"), default=None),
            "popularity": _as_float(base.get("popularity"), default=None),
        },
    }


def _highlight_payload(item: dict[str, Any], base: dict[str, Any]) -> str:
    snippet = _as_str(base.get("review_snippet") or item.get("review_snippet"), default="")
    if snippet:
        return snippet
    overview = _as_str(base.get("overview") or item.get("overview"), default="")
    if not overview:
        return ""
    pieces = re.split(r"(?<=[.!?])\s+", overview)
    first = pieces[0] if pieces else overview
    return first[:177] + "..." if len(first) > 180 else first


def _source_movie_payload(item: dict[str, Any], movie_by_id: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    raw = item.get("source_movie")
    if isinstance(raw, dict):
        mid = _as_int(raw.get("movieId"), default=None)
        base = movie_by_id.get(mid or -1, raw)
        if mid or _as_str(raw.get("title"), default=""):
            return {
                "movieId": mid,
                "title": _as_str(raw.get("title"), default=_as_str(base.get("title"), default="")),
                "year": _as_int(raw.get("year"), default=_as_int(base.get("year"), default=None)),
                "genres": _as_str(raw.get("genres"), default=_as_str(base.get("genres"), default="")),
                "poster_url": _sanitize_poster_url(raw.get("poster_url") or base.get("poster_url") or PLACEHOLDER_POSTER),
            }
    reason = _as_str(item.get("reason"), default="")
    match = re.search(r"Because you (?:liked|watched)\s+(.+)", reason, flags=re.I)
    if not match:
        return None
    title = match.group(1).strip().strip("'\"<>. ")
    for movie in movie_by_id.values():
        if _as_str(movie.get("title"), default="").lower() == title.lower():
            return {
                "movieId": movie.get("movieId"),
                "title": movie.get("title"),
                "year": movie.get("year"),
                "genres": movie.get("genres"),
                "poster_url": movie.get("poster_url") or PLACEHOLDER_POSTER,
            }
    return {"movieId": None, "title": title, "poster_url": PLACEHOLDER_POSTER}


def _clean_movie_row(row: pd.Series, ml_genres_by_movie: dict[int, str]) -> dict[str, Any]:
    poster_url = _sanitize_poster_url(row.get("poster_url"))
    backdrop_url = _sanitize_backdrop_url(row.get("backdrop_url"))
    movie_id = _as_int(row.get("movieId"), default=0)
    fallback_genres = ml_genres_by_movie.get(int(movie_id or 0), "")
    return {
        "movieId": movie_id,
        "tmdbId": _as_int(row.get("tmdbId"), default=None),
        "title": _as_str(row.get("title"), default="Unknown Movie"),
        "year": _as_int(row.get("year"), default=None),
        "genres": _clean_genres(row.get("genres"), fallback=fallback_genres),
        "overview": _as_str(row.get("overview"), default=""),
        "poster_url": poster_url,
        "backdrop_url": backdrop_url,
        "vote_average": _as_float(row.get("vote_average"), default=None),
        "vote_count": _as_int(row.get("vote_count"), default=None),
        "popularity": _as_float(row.get("popularity"), default=None),
        "rating_avg": None,
        "rating_count": None,
        "review_snippet": "",
        "reviews": [],
        "reason_type": "",
        "evidence": "",
        "score_breakdown": {},
        "source_movie": None,
        "user_rating": None,
        "highlight": "",
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
    train_ratings_csv: str = "data/processed/train_ratings.csv",
    test_ratings_csv: str = "data/processed/test_ratings.csv",
    tags_csv: str | None = None,
) -> None:
    out_path = ensure_dir(out_dir)
    movies_df = pd.read_csv(movies_csv)
    ml_genres_by_movie = _movielens_genres_context()
    movies = [_clean_movie_row(row, ml_genres_by_movie) for _, row in movies_df.iterrows()]
    movie_by_id = {m["movieId"]: m for m in movies}
    movie_ids = {int(m["movieId"]) for m in movies if m.get("movieId")}
    ratings_by_movie = _rating_context(train_ratings_csv, test_ratings_csv)
    if tags_csv is None:
        tags_path = _find_first_existing(
            [
                "data/raw/ml-latest-small/tags.csv",
                "data/raw/ml-latest/tags.csv",
                "data/raw/ml-latest/ml-latest/tags.csv",
            ]
        )
        tags_csv = str(tags_path) if tags_path else None
    tags_by_movie = _tag_context(tags_csv, movie_ids)
    for movie in movies:
        mid = int(movie["movieId"])
        movie.update(ratings_by_movie.get(mid, {}))
        movie.update(tags_by_movie.get(mid, {}))
        movie["highlight"] = _highlight_payload(movie, movie)

    rec_cache_path = Path(recommendations_cache_json)
    rec_cache = _load_json_or_default(rec_cache_path, default={})
    if not isinstance(rec_cache, dict):
        rec_cache = {}

    home_cache = rec_cache.get("home_cache", {})
    if not home_cache:
        fallback_home = _load_json_or_default(Path("data/outputs/cache/home_cache.json"), default={})
        if isinstance(fallback_home, dict):
            home_cache = fallback_home

    eval_payload = _load_json_or_default(Path("data/outputs/cache/evaluation_results.json"), default=None)
    if not isinstance(eval_payload, dict):
        eval_df = pd.read_csv(evaluation_csv) if Path(evaluation_csv).exists() else pd.DataFrame()
        eval_items = eval_df.to_dict(orient="records") if not eval_df.empty else []
        eval_payload = {
            "full_ranking": eval_items,
            "sampled_ranking": [],
            "rating_prediction": [],
            "best_hybrid_weights": {},
            "notes": {},
        }

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
            mid = _as_int(it.get("movieId"), default=None)
            if mid is None:
                continue
            base = movie_by_id.get(mid, {})
            title = _as_str(it.get("title"), default=_as_str(base.get("title"), default="Unknown Movie"))
            if _is_unknown_title(title):
                # Drop low-quality rows from static recommendation payloads.
                continue
            poster_url = _sanitize_poster_url(base.get("poster_url") or it.get("poster_url") or PLACEHOLDER_POSTER)
            backdrop_url = _sanitize_backdrop_url(base.get("backdrop_url") or it.get("backdrop_url"))
            out.append(
                {
                    "movieId": mid,
                    "tmdbId": base.get("tmdbId"),
                    "title": title,
                    "year": _as_int(it.get("year"), default=_as_int(base.get("year"), default=None)),
                    "genres": _clean_genres(
                        it.get("genres"),
                        fallback=_as_str(base.get("genres"), default=ml_genres_by_movie.get(mid, "")),
                    ),
                    "overview": _as_str(it.get("overview"), default=_as_str(base.get("overview"), default="")),
                    "poster_url": poster_url,
                    "backdrop_url": backdrop_url,
                    "vote_average": _as_float(base.get("vote_average"), default=None),
                    "vote_count": _as_int(base.get("vote_count"), default=None),
                    "popularity": _as_float(base.get("popularity"), default=None),
                    "rating_avg": _as_float(base.get("rating_avg"), default=None),
                    "rating_count": _as_int(base.get("rating_count"), default=None),
                    "review_snippet": _as_str(base.get("review_snippet"), default=""),
                    "reviews": base.get("reviews") if isinstance(base.get("reviews"), list) else [],
                    "score": _as_float(it.get("score"), default=None),
                    "reason": _as_str(it.get("reason"), default=""),
                    "source_movie": _source_movie_payload(it, movie_by_id),
                    "user_rating": _as_float(it.get("user_rating"), default=None),
                    "highlight": _highlight_payload(it, base),
                    **_reason_payload(it, base),
                }
            )
        return out

    for user_id, payload in list(home_cache.items()):
        if not isinstance(payload, dict):
            continue
        if payload.get("hero_movie"):
            hero_items = _normalize_items([payload["hero_movie"]])
            payload["hero_movie"] = hero_items[0] if hero_items else None
        for sec in ["for_you", "trending", "highly_rated", "because_you_like"]:
            payload[sec] = _normalize_items(payload.get(sec, []))
        rows = payload.get("genre_rows", [])
        if isinstance(rows, list):
            cleaned_rows = []
            for row in rows:
                genre = _as_str(row.get("genre"), default="")
                if genre not in ALLOWED_GENRES:
                    continue
                row["movies"] = _normalize_items(row.get("movies", []))
                if row["movies"]:
                    cleaned_rows.append(row)
            payload["genre_rows"] = cleaned_rows

    if "users" in rec_cache and isinstance(rec_cache["users"], dict):
        for _, user_payload in rec_cache["users"].items():
            if not isinstance(user_payload, dict):
                continue
            for k, v in list(user_payload.items()):
                if isinstance(v, list):
                    user_payload[k] = _normalize_items(v)

    users_cached = len(rec_cache.get("users", {})) if isinstance(rec_cache.get("users"), dict) else len(home_cache)
    build_info = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": "MovieLens + The Movies Dataset + TMDB build-time enrichment",
        "movies_cached": len(movies),
        "users_cached": users_cached,
        "tmdb_enriched": sum(1 for m in movies if _as_int(m.get("tmdbId"), default=None) is not None),
    }

    write_json(out_path / "movies.json", _sanitize_for_json(movies))
    write_json(out_path / "home_cache.json", _sanitize_for_json(home_cache))
    write_json(out_path / "recommendations_cache.json", _sanitize_for_json(rec_cache))
    write_json(out_path / "evaluation_results.json", _sanitize_for_json(eval_payload))
    write_json(out_path / "evaluation_results_legacy.json", _sanitize_for_json(eval_payload.get("full_ranking", [])))
    write_json(out_path / "evaluation_full_ranking.json", _sanitize_for_json(eval_payload.get("full_ranking", [])))
    write_json(out_path / "evaluation_sampled_ranking.json", _sanitize_for_json(eval_payload.get("sampled_ranking", [])))
    write_json(out_path / "search_index.json", _sanitize_for_json(search_index))
    write_json(out_path / "build_info.json", _sanitize_for_json(build_info))
    logger.info("Static data exported to %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export static JSON data for frontend")
    parser.add_argument("--movies", default="data/processed/movies_enriched_with_tmdb.csv")
    parser.add_argument("--recommendations", default="data/outputs/cache/recommendations_cache.json")
    parser.add_argument("--evaluation", default="reports/tables/evaluation_results.csv")
    parser.add_argument("--output-dir", default="frontend/public/data")
    parser.add_argument("--train-ratings", default="data/processed/train_ratings.csv")
    parser.add_argument("--test-ratings", default="data/processed/test_ratings.csv")
    parser.add_argument("--tags", default=None)
    args = parser.parse_args()
    run(
        movies_csv=args.movies,
        recommendations_cache_json=args.recommendations,
        evaluation_csv=args.evaluation,
        out_dir=args.output_dir,
        train_ratings_csv=args.train_ratings,
        test_ratings_csv=args.test_ratings,
        tags_csv=args.tags,
    )


if __name__ == "__main__":
    main()
