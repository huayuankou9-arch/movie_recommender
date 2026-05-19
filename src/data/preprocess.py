from __future__ import annotations

import pandas as pd

from src.utils.text import clean_title, extract_year_from_title


def preprocess_movielens(
    ratings: pd.DataFrame, movies: pd.DataFrame, tags: pd.DataFrame, links: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ratings = ratings.copy()
    movies = movies.copy()
    tags = tags.copy()
    links = links.copy()

    ratings["timestamp"] = pd.to_datetime(ratings["timestamp"], unit="s", errors="coerce")
    tags["timestamp"] = pd.to_datetime(tags["timestamp"], unit="s", errors="coerce")

    movies["year"] = movies["title"].apply(extract_year_from_title)
    movies["clean_title"] = movies["title"].apply(clean_title)
    movies["genres_list"] = movies["genres"].fillna("").apply(
        lambda x: [g.strip() for g in str(x).split("|") if g.strip() and g != "(no genres listed)"]
    )
    movies["genres"] = movies["genres_list"].apply(lambda x: ", ".join(x))

    tag_agg = (
        tags.groupby("movieId", as_index=False)["tag"]
        .apply(lambda s: " ".join(sorted({str(v).strip().lower() for v in s if str(v).strip()})))
        .rename(columns={"tag": "tag_text"})
    )
    movies = movies.merge(tag_agg, on="movieId", how="left")
    movies["tag_text"] = movies["tag_text"].fillna("")

    links["tmdbId"] = pd.to_numeric(links["tmdbId"], errors="coerce").astype("Int64")
    links["imdbId"] = links["imdbId"].astype("Int64")
    movies = movies.merge(links[["movieId", "imdbId", "tmdbId"]], on="movieId", how="left")
    return ratings, movies
