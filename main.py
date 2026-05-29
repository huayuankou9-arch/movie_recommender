from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd
from scipy.sparse import load_npz

from src.data.load_data import load_movielens, load_movies_metadata
from src.data.merge_metadata import merge_movies_with_metadata
from src.data.preprocess import preprocess_movielens
from src.data.split import build_and_save_matrix, train_val_test_split_by_time
from src.evaluation.evaluate import evaluate_models, tune_hybrid_weights
from src.models.content_based import ContentBasedRecommender
from src.models.hybrid import HybridRecommender
from src.models.itemcf import ItemCFRecommender
from src.models.matrix_factorization import MatrixFactorizationRecommender
from src.models.popularity import PopularityRecommender
from src.models.usercf import UserCFRecommender
from src.service.recommender_service import RecommenderService
from src.utils.io import ensure_dir, read_json, read_yaml, write_json
from src.utils.logger import get_logger

logger = get_logger("main")


def _cfg():
    return read_yaml("config.yaml")


def _resolve_data_dir(primary: str, candidates: list[str], required_files: list[str]) -> str:
    ordered = [primary] + candidates
    for idx, cand in enumerate(ordered):
        p = Path(cand)
        if not p.exists():
            continue
        if all((p / f).exists() for f in required_files):
            if idx > 0:
                logger.warning("Configured path %s invalid for required files, fallback to %s", primary, cand)
            return str(p)
    return str(Path(primary))


def run_preprocess(cfg: dict) -> None:
    processed_dir = ensure_dir(cfg["data"]["processed_dir"])
    movielens_dir = _resolve_data_dir(
        cfg["data"]["movielens_dir"],
        ["data/raw/ml-latest-small", "data/raw/ml-latest/ml-latest", "data/raw/ml-latest"],
        ["ratings.csv", "movies.csv", "tags.csv", "links.csv"],
    )
    metadata_dir = _resolve_data_dir(
        cfg["data"]["metadata_dir"],
        ["data/raw/the-movies-dataset", "data/raw/the-movie-dataset"],
        ["movies_metadata.csv", "keywords.csv", "credits.csv", "links_small.csv"],
    )
    movielens = load_movielens(movielens_dir)
    ratings, movies_ml = preprocess_movielens(
        movielens["ratings"], movielens["movies"], movielens["tags"], movielens["links"]
    )
    ratings, movies_ml = _maybe_downsample_movielens(
        ratings,
        movies_ml,
        max_users=int(cfg.get("data", {}).get("max_users_for_training", 3000)),
        max_ratings=int(cfg.get("data", {}).get("max_ratings_for_training", 600000)),
        min_movie_ratings=int(cfg.get("data", {}).get("min_movie_ratings_after_sampling", 5)),
    )

    try:
        meta = load_movies_metadata(metadata_dir)
        movies_enriched = merge_movies_with_metadata(
            movies_ml=movies_ml,
            movies_metadata=meta["movies_metadata"],
            keywords=meta["keywords"],
            credits=meta["credits"],
            links_small=meta["links_small"],
            tmdb_cfg=cfg["tmdb"],
            default_poster=cfg["app"]["default_poster"],
            default_backdrop=cfg["app"]["default_backdrop"],
        )
    except FileNotFoundError:
        logger.warning("The Movies Dataset not found, using MovieLens-only metadata fallback.")
        movies_enriched = movies_ml.copy()
        movies_enriched["overview"] = ""
        movies_enriched["keywords"] = ""
        movies_enriched["cast"] = ""
        movies_enriched["director"] = ""
        movies_enriched["poster_url"] = cfg["app"]["default_poster"]
        movies_enriched["backdrop_url"] = cfg["app"]["default_backdrop"]
        movies_enriched["release_date"] = ""
        movies_enriched["runtime"] = None
        movies_enriched["vote_average"] = None
        movies_enriched["vote_count"] = None
        movies_enriched["popularity"] = None
        movies_enriched["metadata_text"] = (
            movies_enriched["title"].fillna("")
            + " "
            + movies_enriched["genres"].fillna("")
            + " "
            + movies_enriched["tag_text"].fillna("")
        ).str.lower()
        movies_enriched = movies_enriched[
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
                "poster_url",
                "backdrop_url",
                "release_date",
                "runtime",
                "vote_average",
                "vote_count",
                "popularity",
                "metadata_text",
            ]
        ]

    train, val, test = train_val_test_split_by_time(
        ratings,
        train_ratio=float(cfg["split"].get("train_ratio", 0.7)),
        val_ratio=float(cfg["split"].get("val_ratio", 0.1)),
        test_ratio=float(cfg["split"].get("test_ratio", 0.2)),
    )
    if cfg.get("content", {}).get("use_weighted_fields", True):
        movies_enriched["metadata_text"] = (
            (movies_enriched["genres"].fillna("").astype(str) + " ") * 3
            + (movies_enriched["tag_text"].fillna("").astype(str) + " ") * 3
            + (movies_enriched.get("keywords", "").fillna("").astype(str) + " ") * 2
            + movies_enriched.get("overview", "").fillna("").astype(str)
            + " "
            + movies_enriched.get("cast", "").fillna("").astype(str)
            + " "
            + movies_enriched.get("director", "").fillna("").astype(str)
        ).str.lower()
    train.to_csv(processed_dir / "train_ratings.csv", index=False)
    val.to_csv(processed_dir / "validation_ratings.csv", index=False)
    test.to_csv(processed_dir / "test_ratings.csv", index=False)
    movies_enriched.to_csv(processed_dir / "movies_enriched.csv", index=False)
    build_and_save_matrix(train, processed_dir)
    logger.info("Preprocess complete.")


def _maybe_downsample_movielens(
    ratings: pd.DataFrame,
    movies_ml: pd.DataFrame,
    max_users: int = 3000,
    max_ratings: int = 600000,
    min_movie_ratings: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    total = len(ratings)
    if total <= max_ratings:
        return ratings, movies_ml
    logger.warning(
        "ratings size=%s exceeds max_ratings=%s, downsampling users for practical training runtime.",
        total,
        max_ratings,
    )
    user_counts = ratings.groupby("userId")["movieId"].count().sort_values(ascending=False)
    keep_users = user_counts.head(max_users).index
    sampled = ratings[ratings["userId"].isin(keep_users)].copy()
    if len(sampled) > max_ratings:
        sampled = (
            sampled.sort_values("timestamp")
            .groupby("userId", group_keys=False)
            .tail(max(20, max_ratings // max_users))
            .copy()
        )
    if min_movie_ratings > 1:
        movie_counts = sampled.groupby("movieId")["userId"].count()
        keep_movies = movie_counts[movie_counts >= min_movie_ratings].index
        sampled = sampled[sampled["movieId"].isin(keep_movies)].copy()
    sampled_movies = sampled["movieId"].unique()
    movies_small = movies_ml[movies_ml["movieId"].isin(sampled_movies)].copy()
    logger.warning(
        "downsampled to users=%s ratings=%s movies=%s",
        sampled["userId"].nunique(),
        len(sampled),
        len(movies_small),
    )
    return sampled, movies_small


def _load_matrix_bundle(processed_dir: Path) -> dict:
    return {
        "matrix": load_npz(processed_dir / "user_item_matrix.npz"),
        "user_encoder": joblib.load(processed_dir / "user_encoder.pkl"),
        "movie_encoder": joblib.load(processed_dir / "movie_encoder.pkl"),
        "user_decoder": joblib.load(processed_dir / "user_decoder.pkl"),
        "movie_decoder": joblib.load(processed_dir / "movie_decoder.pkl"),
    }


def run_train(cfg: dict) -> None:
    processed_dir = Path(cfg["data"]["processed_dir"])
    output_models_dir = ensure_dir(Path(cfg["data"]["output_dir"]) / "models")
    train = pd.read_csv(processed_dir / "train_ratings.csv")
    movies = pd.read_csv(processed_dir / "movies_enriched.csv")
    matrix_bundle = _load_matrix_bundle(processed_dir)

    pop = PopularityRecommender(movies, min_rating_count=cfg["models"]["min_rating_count"])
    pop.fit(train)

    usercf_cfg = cfg.get("usercf", {})
    usercf = UserCFRecommender(
        movies,
        top_k_neighbors=int(usercf_cfg.get("neighbors", cfg["models"]["usercf_neighbors"])),
        shrinkage=float(usercf_cfg.get("shrinkage", 10)),
        min_common_items=int(usercf_cfg.get("min_common_items", 2)),
    )
    usercf.fit(train, matrix_bundle)

    itemcf_cfg = cfg.get("itemcf", {})
    itemcf = ItemCFRecommender(
        movies,
        top_n_similar=int(itemcf_cfg.get("neighbors", cfg["models"]["itemcf_neighbors"])),
        positive_threshold=float(cfg["split"].get("positive_threshold", 4.0)),
        use_positive_history_only=bool(itemcf_cfg.get("use_positive_history_only", True)),
        normalize_scores=bool(itemcf_cfg.get("normalize_scores", True)),
    )
    itemcf.fit(train, matrix_bundle)

    mf_cfg = cfg.get("mf", {})
    mf = MatrixFactorizationRecommender(
        movies,
        n_factors=int(mf_cfg.get("factors", cfg["models"]["mf_factors"])),
        n_epochs=int(mf_cfg.get("epochs", cfg["models"]["mf_epochs"])),
        lr=float(mf_cfg.get("lr", 0.005)),
        reg=float(mf_cfg.get("reg", 0.05)),
    )
    mf.fit(train, matrix_bundle)

    content_cfg = cfg.get("content", {})
    content = ContentBasedRecommender(
        movies,
        positive_threshold=cfg["split"]["positive_threshold"],
        max_features=int(content_cfg.get("max_features", 30000)),
        ngram_range=tuple(content_cfg.get("ngram_range", [1, 2])),
        use_weighted_fields=bool(content_cfg.get("use_weighted_fields", True)),
    )
    content.fit(train)

    hybrid = HybridRecommender(
        movies,
        popularity_model=pop,
        usercf_model=usercf,
        itemcf_model=itemcf,
        mf_model=mf,
        content_model=content,
        weights=cfg["hybrid"].get("default_weights", cfg["hybrid"]),
        recall_top=int(cfg.get("hybrid", {}).get("recall_top", 200)),
    )
    hybrid.fit()

    pop.save(output_models_dir / "popularity.pkl")
    usercf.save(output_models_dir / "usercf.pkl")
    itemcf.save(output_models_dir / "itemcf.pkl")
    mf.save(output_models_dir / "mf.pkl")
    content.save(output_models_dir / "content.pkl")
    hybrid.save(output_models_dir / "hybrid.pkl")
    logger.info("Training complete. Models saved to %s", output_models_dir)


def _load_models(cfg: dict, movies: pd.DataFrame):
    output_models_dir = Path(cfg["data"]["output_dir"]) / "models"
    return {
        "Popularity": PopularityRecommender.load(output_models_dir / "popularity.pkl"),
        "UserCF": UserCFRecommender.load(output_models_dir / "usercf.pkl"),
        "ItemCF": ItemCFRecommender.load(output_models_dir / "itemcf.pkl"),
        "MatrixFactorization": MatrixFactorizationRecommender.load(output_models_dir / "mf.pkl"),
        "ContentBased": ContentBasedRecommender.load(output_models_dir / "content.pkl"),
        "Hybrid": HybridRecommender.load(output_models_dir / "hybrid.pkl"),
    }


def run_evaluate(cfg: dict) -> pd.DataFrame:
    processed_dir = Path(cfg["data"]["processed_dir"])
    train = pd.read_csv(processed_dir / "train_ratings.csv")
    test = pd.read_csv(processed_dir / "test_ratings.csv")
    movies = pd.read_csv(processed_dir / "movies_enriched.csv")

    models = _load_models(cfg, movies)
    table_path = Path("reports/tables/evaluation_results.csv")
    fig_path = Path("reports/figures/metrics_comparison.png")
    best_weights_path = Path(cfg["data"]["output_dir"]) / "models" / "hybrid_best_weights.json"
    best_weights = read_json(best_weights_path) if best_weights_path.exists() else {}
    result = evaluate_models(
        models=models,
        train_ratings=train,
        test_ratings=test,
        movies_df=movies,
        output_table_path=table_path,
        output_figure_path=fig_path,
        k=cfg["evaluation"]["k"],
        positive_threshold=cfg.get("evaluation", {}).get("positive_threshold", cfg["split"]["positive_threshold"]),
        max_users=cfg.get("evaluation", {}).get("max_eval_users", cfg.get("evaluation", {}).get("max_users")),
        sampled_cfg=cfg.get("evaluation", {}).get("sampled_eval", {}),
        best_hybrid_weights=best_weights,
    )
    ensure_dir(Path(cfg["data"]["output_dir"]) / "cache")
    write_json(Path(cfg["data"]["output_dir"]) / "cache" / "evaluation_results.json", result)
    write_json(Path(cfg["data"]["output_dir"]) / "cache" / "evaluation_results_legacy.json", result["full_ranking"])
    logger.info("Evaluation complete.")
    return result


def run_tune_hybrid(cfg: dict) -> dict:
    processed_dir = Path(cfg["data"]["processed_dir"])
    train = pd.read_csv(processed_dir / "train_ratings.csv")
    val = pd.read_csv(processed_dir / "validation_ratings.csv")
    movies = pd.read_csv(processed_dir / "movies_enriched.csv")
    models = _load_models(cfg, movies)
    candidates = cfg.get("hybrid", {}).get("candidate_weights", [cfg.get("hybrid", {}).get("default_weights", {})])
    best = tune_hybrid_weights(
        models,
        train,
        val,
        movies,
        candidate_weights=candidates,
        k=int(cfg.get("evaluation", {}).get("k", 10)),
        positive_threshold=float(cfg.get("evaluation", {}).get("positive_threshold", cfg["split"]["positive_threshold"])),
        max_users=min(int(cfg.get("evaluation", {}).get("sampled_eval", {}).get("max_users", 1000)), 300),
    )
    output_models_dir = ensure_dir(Path(cfg["data"]["output_dir"]) / "models")
    write_json(output_models_dir / "hybrid_best_weights.json", best)
    if "Hybrid" in models:
        models["Hybrid"].set_weights(best)
        models["Hybrid"].save(output_models_dir / "hybrid.pkl")
    logger.info("Hybrid tuning complete. Best weights=%s", best)
    return best


def run_cache(cfg: dict) -> None:
    processed_dir = Path(cfg["data"]["processed_dir"])
    movies = pd.read_csv(processed_dir / "movies_enriched.csv")
    models = _load_models(cfg, movies)
    output_cache = ensure_dir(Path(cfg["data"]["output_dir"]) / "cache")
    hybrid = models["Hybrid"]
    pop = models["Popularity"]

    users = cfg.get("app", {}).get("cache_users", [1, 2, 3])
    home_cache = {}
    recommendations_cache: dict[str, object] = {"users": {}, "home_cache": home_cache}
    for uid in users:
        try:
            uid_int = int(uid)
            recs = hybrid.recommend(uid_int, top_k=12, exclude_seen=True)
            pop_recs = pop.recommend(uid_int, top_k=12, exclude_seen=True)
            usercf_recs = models["UserCF"].recommend(uid_int, top_k=12, exclude_seen=True)
            itemcf_recs = models["ItemCF"].recommend(uid_int, top_k=12, exclude_seen=True)
            mf_recs = models["MatrixFactorization"].recommend(uid_int, top_k=12, exclude_seen=True)
            content_recs = models["ContentBased"].recommend(uid_int, top_k=12, exclude_seen=True)

            home_cache[str(uid)] = {
                "hero_movie": recs[0] if recs else None,
                "for_you": recs,
                "trending": pop.recommend_trending(12),
                "highly_rated": pop.recommend_highly_rated(12),
                "because_you_like": itemcf_recs,
                "genre_rows": RecommenderService.get_instance()._genre_rows(uid_int, top_k=12),
            }
            recommendations_cache["users"][str(uid)] = {
                "popularity": pop_recs,
                "usercf": usercf_recs,
                "itemcf": itemcf_recs,
                "mf": mf_recs,
                "content": content_recs,
                "hybrid": recs,
            }
        except Exception:
            continue
    write_json(output_cache / "home_cache.json", home_cache)
    write_json(output_cache / "popular_movies.json", pop.recommend_trending(40))
    write_json(output_cache / "recommendations_cache.json", recommendations_cache)
    logger.info("Cache generated.")


def run_fetch_tmdb(cfg: dict) -> None:
    from scripts.fetch_tmdb_metadata import run as fetch_tmdb_run

    input_csv = str(Path(cfg["data"]["processed_dir"]) / "movies_enriched.csv")
    output_csv = str(Path(cfg["data"]["processed_dir"]) / "movies_enriched_with_tmdb.csv")
    cache_json = str(Path(cfg["data"]["processed_dir"]) / "tmdb_cache.json")
    fetch_tmdb_run(
        input_csv=input_csv,
        output_csv=output_csv,
        cache_json=cache_json,
        limit=int(cfg.get("tmdb", {}).get("fetch_limit", 1000)),
        force=bool(cfg.get("tmdb", {}).get("force_fetch", False)),
        verify_posters=bool(cfg.get("tmdb", {}).get("verify_posters", True)),
        verify_workers=int(cfg.get("tmdb", {}).get("verify_workers", 64)),
        fetch_workers=int(cfg.get("tmdb", {}).get("fetch_workers", 32)),
        batch_size=int(cfg.get("tmdb", {}).get("batch_size", 500)),
    )


def run_export_static(cfg: dict) -> None:
    from scripts.export_static_data import run as export_static_run

    processed_dir = Path(cfg["data"]["processed_dir"])
    movies_tmdb = processed_dir / "movies_enriched_with_tmdb.csv"
    movies_base = processed_dir / "movies_enriched.csv"
    movies_csv = str(movies_tmdb if movies_tmdb.exists() else movies_base)
    recommendations = str(Path(cfg["data"]["output_dir"]) / "cache" / "recommendations_cache.json")
    evaluation = "reports/tables/evaluation_results.csv"
    export_static_run(
        movies_csv=movies_csv,
        recommendations_cache_json=recommendations,
        evaluation_csv=evaluation,
        out_dir="frontend/public/data",
    )


def main():
    parser = argparse.ArgumentParser(description="Movie recommender pipeline")
    parser.add_argument(
        "command",
        choices=["preprocess", "train", "tune-hybrid", "evaluate", "all", "fetch-tmdb", "export-static", "build-static"],
    )
    args = parser.parse_args()

    cfg = _cfg()
    try:
        if args.command == "preprocess":
            run_preprocess(cfg)
        elif args.command == "train":
            run_train(cfg)
        elif args.command == "tune-hybrid":
            run_tune_hybrid(cfg)
        elif args.command == "evaluate":
            run_evaluate(cfg)
        elif args.command == "all":
            run_preprocess(cfg)
            run_train(cfg)
            run_tune_hybrid(cfg)
            run_evaluate(cfg)
            run_cache(cfg)
            run_export_static(cfg)
        elif args.command == "fetch-tmdb":
            run_fetch_tmdb(cfg)
        elif args.command == "export-static":
            run_export_static(cfg)
        elif args.command == "build-static":
            run_preprocess(cfg)
            run_train(cfg)
            run_tune_hybrid(cfg)
            run_evaluate(cfg)
            run_cache(cfg)
            run_fetch_tmdb(cfg)
            run_export_static(cfg)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
