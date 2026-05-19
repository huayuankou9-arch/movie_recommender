from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import re

from src.utils.text import safe_literal_eval


def _extract_names(payload: Any, limit: int | None = None) -> list[str]:
    arr = safe_literal_eval(payload, fallback=[])
    if not isinstance(arr, list):
        return []
    names: list[str] = []
    for item in arr:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]).strip())
    if limit is not None:
        names = names[:limit]
    return names


def _extract_director(crew_payload: Any) -> str:
    crew = safe_literal_eval(crew_payload, fallback=[])
    if not isinstance(crew, list):
        return ""
    for member in crew:
        if isinstance(member, dict) and str(member.get("job", "")).lower() == "director":
            return str(member.get("name", "")).strip()
    return ""


def _safe_int_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def merge_movies_with_metadata(
    movies_ml: pd.DataFrame,
    movies_metadata: pd.DataFrame,
    keywords: pd.DataFrame,
    credits: pd.DataFrame,
    links_small: pd.DataFrame,
    tmdb_cfg: dict,
    default_poster: str,
    default_backdrop: str,
) -> pd.DataFrame:
    meta = movies_metadata.copy()
    keys = keywords.copy()
    cre = credits.copy()
    lsmall = links_small.copy()
    ml = movies_ml.copy()

    meta["id"] = _safe_int_series(meta["id"])
    keys["id"] = _safe_int_series(keys["id"])
    cre["id"] = _safe_int_series(cre["id"])
    lsmall["tmdbId"] = _safe_int_series(lsmall["tmdbId"])

    required_meta_cols = [
        "id",
        "imdb_id",
        "title",
        "original_title",
        "overview",
        "poster_path",
        "backdrop_path",
        "release_date",
        "runtime",
        "vote_average",
        "vote_count",
        "popularity",
        "production_companies",
        "production_countries",
        "spoken_languages",
        "genres",
    ]
    for col in required_meta_cols:
        if col not in meta.columns:
            meta[col] = np.nan if col not in {"overview", "poster_path", "backdrop_path", "title", "original_title"} else ""

    meta["genres_names"] = meta["genres"].apply(_extract_names)
    meta["release_date"] = pd.to_datetime(meta["release_date"], errors="coerce")
    meta["release_year"] = meta["release_date"].dt.year
    meta["runtime"] = pd.to_numeric(meta["runtime"], errors="coerce")
    meta["vote_average"] = pd.to_numeric(meta["vote_average"], errors="coerce")
    meta["vote_count"] = pd.to_numeric(meta["vote_count"], errors="coerce")
    meta["popularity"] = pd.to_numeric(meta["popularity"], errors="coerce")

    keys["keywords_names"] = keys["keywords"].apply(_extract_names)
    cre["cast_names"] = cre["cast"].apply(lambda x: _extract_names(x, limit=3))
    cre["director"] = cre["crew"].apply(_extract_director)

    enrich = (
        meta[
            [
                "id",
                "imdb_id",
                "title",
                "original_title",
                "overview",
                "poster_path",
                "backdrop_path",
                "release_date",
                "release_year",
                "runtime",
                "vote_average",
                "vote_count",
                "popularity",
                "production_companies",
                "production_countries",
                "spoken_languages",
                "genres_names",
            ]
        ]
        .merge(keys[["id", "keywords_names"]], on="id", how="left")
        .merge(cre[["id", "cast_names", "director"]], on="id", how="left")
    )

    img_base = tmdb_cfg["image_base_url"]
    poster_size = tmdb_cfg["poster_size"]
    backdrop_size = tmdb_cfg["backdrop_size"]
    def _is_valid_img_path(p: Any) -> bool:
        if not isinstance(p, str):
            return False
        p = p.strip()
        return bool(re.match(r"^/[^\\]+\.(jpg|jpeg|png|webp)$", p, flags=re.IGNORECASE))

    enrich["poster_url"] = enrich["poster_path"].apply(
        lambda p: f"{img_base}/{poster_size}{p.strip()}" if _is_valid_img_path(p) else default_poster
    )
    enrich["backdrop_url"] = enrich["backdrop_path"].apply(
        lambda p: f"{img_base}/{backdrop_size}{p.strip()}" if _is_valid_img_path(p) else default_backdrop
    )

    ml["tmdbId"] = _safe_int_series(ml["tmdbId"])
    merged = ml.merge(enrich, left_on="tmdbId", right_on="id", how="left")

    tmdb_to_meta = lsmall[["movieId", "tmdbId"]].dropna().drop_duplicates()
    tmdb_to_meta["movieId"] = _safe_int_series(tmdb_to_meta["movieId"])
    merged2 = merged.merge(tmdb_to_meta, on="movieId", how="left", suffixes=("", "_lsmall"))
    fill_mask = merged2["id"].isna() & merged2["tmdbId_lsmall"].notna()
    if fill_mask.any():
        backfill = enrich.rename(columns={"id": "tmdbId_lsmall"})
        merged2 = merged2.merge(backfill, on="tmdbId_lsmall", how="left", suffixes=("", "_bf"))
        for col in [
            "overview",
            "poster_url",
            "backdrop_url",
            "runtime",
            "vote_average",
            "vote_count",
            "popularity",
            "release_date",
            "release_year",
            "genres_names",
            "keywords_names",
            "cast_names",
            "director",
        ]:
            merged2[col] = np.where(merged2[col].notna(), merged2[col], merged2[f"{col}_bf"])
        merged2["id"] = np.where(merged2["id"].notna(), merged2["id"], merged2["tmdbId_lsmall"])
        drop_cols = [c for c in merged2.columns if c.endswith("_bf")]
        merged2 = merged2.drop(columns=drop_cols)

    merged2["genres_names"] = merged2["genres_names"].apply(
        lambda x: x if isinstance(x, list) and x else [g.strip() for g in str(x).split(",") if g.strip()]
    )
    merged2["keywords_names"] = merged2["keywords_names"].apply(lambda x: x if isinstance(x, list) else [])
    merged2["cast_names"] = merged2["cast_names"].apply(lambda x: x if isinstance(x, list) else [])
    merged2["director"] = merged2["director"].fillna("")
    merged2["overview"] = merged2["overview"].fillna("")
    merged2["release_date"] = pd.to_datetime(merged2["release_date"], errors="coerce")
    merged2["release_date"] = merged2["release_date"].dt.strftime("%Y-%m-%d").fillna("")

    merged2["genres"] = merged2["genres_names"].apply(lambda x: ", ".join(x) if isinstance(x, list) else "")
    merged2["keywords"] = merged2["keywords_names"].apply(lambda x: ", ".join(x))
    merged2["cast"] = merged2["cast_names"].apply(lambda x: ", ".join(x))
    merged2["release_year"] = pd.to_numeric(merged2["release_year"], errors="coerce")
    merged2["year"] = merged2["year"].fillna(merged2["release_year"]).astype("Int64")

    merged2["metadata_text"] = (
        merged2["title"].fillna("")
        + " "
        + merged2["genres"].fillna("")
        + " "
        + merged2["tag_text"].fillna("")
        + " "
        + merged2["overview"].fillna("")
        + " "
        + merged2["keywords"].fillna("")
        + " "
        + merged2["cast"].fillna("")
        + " "
        + merged2["director"].fillna("")
    ).str.lower()

    out = merged2[
        [
            "movieId",
            "tmdbId",
            "imdbId",
            "title",
            "clean_title",
            "year",
            "genres",
            "tag_text",
            "overview",
            "keywords",
            "cast",
            "director",
            "poster_path",
            "backdrop_path",
            "poster_url",
            "backdrop_url",
            "release_date",
            "runtime",
            "vote_average",
            "vote_count",
            "popularity",
            "metadata_text",
        ]
    ].copy()

    out["poster_url"] = out["poster_url"].fillna(default_poster)
    out["backdrop_url"] = out["backdrop_url"].fillna(default_backdrop)
    out["poster_path"] = out["poster_path"].fillna("")
    out["backdrop_path"] = out["backdrop_path"].fillna("")
    out["year"] = out["year"].astype("Int64")
    out["tmdbId"] = out["tmdbId"].astype("Int64")
    out["imdbId"] = out["imdbId"].astype("Int64")
    return out.drop_duplicates(subset=["movieId"]).reset_index(drop=True)
