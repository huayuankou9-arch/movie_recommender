from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return pd.read_csv(path, **kwargs)


def load_movielens(movielens_dir: str | Path) -> dict[str, pd.DataFrame]:
    base = Path(movielens_dir)
    logger.info("Loading MovieLens data from %s", base)
    ratings = _read_csv(base / "ratings.csv")
    movies = _read_csv(base / "movies.csv")
    tags = _read_csv(base / "tags.csv")
    links = _read_csv(base / "links.csv")
    return {"ratings": ratings, "movies": movies, "tags": tags, "links": links}


def load_movies_metadata(metadata_dir: str | Path) -> dict[str, pd.DataFrame]:
    base = Path(metadata_dir)
    logger.info("Loading The Movies Dataset from %s", base)
    movies_metadata = _read_csv(base / "movies_metadata.csv", low_memory=False)
    keywords = _read_csv(base / "keywords.csv")
    credits = _read_csv(base / "credits.csv")
    links_small = _read_csv(base / "links_small.csv")
    return {
        "movies_metadata": movies_metadata,
        "keywords": keywords,
        "credits": credits,
        "links_small": links_small,
    }
