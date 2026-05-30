from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from datetime import datetime, timezone

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.evaluation.metrics import coverage, hit_rate_at_k, mae, ndcg_at_k, precision_at_k, recall_at_k, rmse
from src.utils.io import ensure_dir, write_json
from src.utils.logger import get_logger

RATING_MODELS = {"UserCF", "ItemCF", "MatrixFactorization"}
SamplingMode = Literal["random", "popaware"]
logger = get_logger("evaluation")


def _score_candidates(model: object, user_id: int, candidates: list[int]) -> dict[int, float]:
    if hasattr(model, "score_items"):
        return getattr(model, "score_items")(user_id, candidates)
    return {mid: float(model.score(user_id, mid)) for mid in candidates}


def _round_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: round(v, 6) if isinstance(v, float) else v for k, v in row.items()}


def _positives_by_user(ratings: pd.DataFrame, positive_threshold: float) -> dict[int, set[int]]:
    return (
        ratings[ratings["rating"] >= positive_threshold]
        .groupby("userId")["movieId"]
        .apply(lambda x: set(x.astype(int).tolist()))
        .to_dict()
    )


def _eligible_users(train_ratings: pd.DataFrame, test_ratings: pd.DataFrame, positive_threshold: float, max_users: int | None, seed: int = 42) -> tuple[list[int], dict[int, set[int]], dict[int, set[int]], dict[int, set[int]]]:
    positives = _positives_by_user(test_ratings, positive_threshold)
    train_seen = train_ratings.groupby("userId")["movieId"].apply(lambda x: set(x.astype(int))).to_dict()
    test_seen = test_ratings.groupby("userId")["movieId"].apply(lambda x: set(x.astype(int))).to_dict()
    users = [int(uid) for uid in positives if uid in train_seen and positives.get(uid)]
    users.sort()
    if max_users and len(users) > max_users:
        rng = np.random.default_rng(seed)
        users = sorted(rng.choice(np.array(users), size=max_users, replace=False).astype(int).tolist())
    return users, positives, train_seen, test_seen


def _popularity_buckets(train_ratings: pd.DataFrame, all_items: np.ndarray, num_buckets: int = 10) -> tuple[dict[int, int], dict[int, list[int]]]:
    counts = train_ratings.groupby("movieId").size().reindex(all_items, fill_value=0).astype(float)
    ranks = counts.rank(method="first")
    bucket_ids = pd.qcut(ranks, q=min(num_buckets, len(counts)), labels=False, duplicates="drop")
    item_to_bucket = {int(mid): int(bucket_ids.loc[mid]) for mid in counts.index}
    bucket_to_items: dict[int, list[int]] = {}
    for mid, bucket in item_to_bucket.items():
        bucket_to_items.setdefault(bucket, []).append(mid)
    return item_to_bucket, bucket_to_items


def _sample_negatives(
    rng: np.random.Generator,
    mode: SamplingMode,
    positives: set[int],
    interacted: set[int],
    all_items: np.ndarray,
    num_negatives: int,
    item_to_bucket: dict[int, int] | None = None,
    bucket_to_items: dict[int, list[int]] | None = None,
    adjacent_buckets: int = 1,
    prefer_harder: bool = False,
) -> list[int]:
    sampled: list[int] = []
    blocked = set(interacted) | set(positives)
    if mode == "random" or not item_to_bucket or not bucket_to_items:
        pool = np.array([mid for mid in all_items if mid not in blocked])
        if len(pool) == 0:
            return []
        n = min(num_negatives * max(1, len(positives)), len(pool))
        return rng.choice(pool, size=n, replace=False).astype(int).tolist()

    used = set(blocked)
    buckets = sorted(bucket_to_items)
    for pos in positives:
        bucket = item_to_bucket.get(int(pos))
        if bucket is None:
            continue
        if prefer_harder:
            candidate_buckets = [b for b in buckets if bucket <= b <= bucket + adjacent_buckets]
        else:
            candidate_buckets = [b for b in buckets if abs(b - bucket) <= adjacent_buckets]
        pool = [mid for b in candidate_buckets for mid in bucket_to_items.get(b, []) if mid not in used]
        if not pool:
            pool = [mid for mid in all_items if mid not in used]
        if not pool:
            continue
        n = min(num_negatives, len(pool))
        picks = rng.choice(np.array(pool), size=n, replace=False).astype(int).tolist()
        sampled.extend(picks)
        used.update(picks)
    return sampled


def rating_prediction_eval(models: dict[str, object], test_ratings: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for model_name, model in models.items():
        if model_name not in RATING_MODELS:
            rows.append({"model": model_name, "rmse": None, "mae": None})
            continue
        y_true, y_pred = [], []
        for uid, group in test_ratings.groupby("userId"):
            movie_ids = group["movieId"].astype(int).tolist()
            if hasattr(model, "score_items"):
                score_map = getattr(model, "score_items")(int(uid), movie_ids)
                preds = [score_map.get(int(mid), np.nan) for mid in movie_ids]
            else:
                preds = [model.score(int(uid), int(mid)) for mid in movie_ids]
            y_true.extend(group["rating"].astype(float).tolist())
            for pred in preds:
                try:
                    value = float(pred)
                except Exception:
                    value = 3.0
                y_pred.append(float(np.clip(value if np.isfinite(value) else 3.0, 0.5, 5.0)))
        rows.append(_round_row({"model": model_name, "rmse": rmse(y_true, y_pred), "mae": mae(y_true, y_pred)}))
    return rows


def _ranking_rows(models: dict[str, object], user_candidates: dict[int, tuple[list[int], set[int]]], all_items: set[int], k: int) -> list[dict[str, Any]]:
    rows = []
    for model_name, model in models.items():
        p_list: list[float] = []
        r_list: list[float] = []
        h_list: list[float] = []
        n_list: list[float] = []
        all_recs: list[int] = []
        for uid, (candidates, pos) in user_candidates.items():
            score_map = _score_candidates(model, uid, candidates)
            scored = [(mid, float(score_map.get(mid, 0.0))) for mid in candidates]
            scored.sort(key=lambda x: x[1], reverse=True)
            rec_ids = [mid for mid, _ in scored[:k]]
            all_recs.extend(rec_ids)
            p_list.append(precision_at_k(rec_ids, pos, k))
            r_list.append(recall_at_k(rec_ids, pos, k))
            h_list.append(hit_rate_at_k(rec_ids, pos, k))
            n_list.append(ndcg_at_k(rec_ids, pos, k))
        rows.append(_round_row({
            "model": model_name,
            "precision@10": float(np.mean(p_list)) if p_list else 0.0,
            "recall@10": float(np.mean(r_list)) if r_list else 0.0,
            "hitrate@10": float(np.mean(h_list)) if h_list else 0.0,
            "ndcg@10": float(np.mean(n_list)) if n_list else 0.0,
            "coverage": coverage(all_recs, all_items),
        }))
    return rows


def full_ranking_eval(models: dict[str, object], train_ratings: pd.DataFrame, test_ratings: pd.DataFrame, movies_df: pd.DataFrame, k: int, positive_threshold: float, max_users: int | None = None, seed: int = 42) -> tuple[list[dict[str, Any]], int]:
    users, positives, _, _ = _eligible_users(train_ratings, test_ratings, positive_threshold, max_users, seed)
    all_items = set(movies_df["movieId"].astype(int).tolist())
    rows = []
    for model_name, model in models.items():
        p_list: list[float] = []
        r_list: list[float] = []
        h_list: list[float] = []
        n_list: list[float] = []
        all_recs: list[int] = []
        for uid in users:
            recs = model.recommend(int(uid), top_k=k, exclude_seen=True)
            rec_ids = [int(x["movieId"]) for x in recs]
            all_recs.extend(rec_ids)
            pos = positives.get(uid, set())
            p_list.append(precision_at_k(rec_ids, pos, k))
            r_list.append(recall_at_k(rec_ids, pos, k))
            h_list.append(hit_rate_at_k(rec_ids, pos, k))
            n_list.append(ndcg_at_k(rec_ids, pos, k))
        rows.append(_round_row({
            "model": model_name,
            "precision@10": float(np.mean(p_list)) if p_list else 0.0,
            "recall@10": float(np.mean(r_list)) if r_list else 0.0,
            "hitrate@10": float(np.mean(h_list)) if h_list else 0.0,
            "ndcg@10": float(np.mean(n_list)) if n_list else 0.0,
            "coverage": coverage(all_recs, all_items),
        }))
    return rows, len(users)


def sampled_ranking_eval(
    models: dict[str, object],
    train_ratings: pd.DataFrame,
    test_ratings: pd.DataFrame,
    movies_df: pd.DataFrame,
    k: int,
    positive_threshold: float,
    num_negatives: int = 99,
    max_users: int | None = 1000,
    seed: int = 42,
    mode: SamplingMode = "random",
    num_buckets: int = 10,
    adjacent_buckets: int = 1,
    prefer_harder: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    rng = np.random.default_rng(seed)
    users, positives, train_seen, test_seen = _eligible_users(train_ratings, test_ratings, positive_threshold, max_users, seed)
    all_items = np.array(movies_df["movieId"].astype(int).unique())
    item_to_bucket = bucket_to_items = None
    if mode == "popaware":
        item_to_bucket, bucket_to_items = _popularity_buckets(train_ratings, all_items, num_buckets=num_buckets)
    user_candidates: dict[int, tuple[list[int], set[int]]] = {}
    for uid in users:
        pos = positives.get(uid, set())
        interacted = set(train_seen.get(uid, set())) | set(test_seen.get(uid, set()))
        negs = _sample_negatives(rng, mode, pos, interacted, all_items, num_negatives, item_to_bucket, bucket_to_items, adjacent_buckets, prefer_harder)
        if not negs:
            continue
        user_candidates[int(uid)] = (list(pos) + negs, pos)
    return _ranking_rows(models, user_candidates, set(all_items.astype(int)), k), len(user_candidates)


def tune_hybrid_weights(models: dict[str, object], train_ratings: pd.DataFrame, val_ratings: pd.DataFrame, movies_df: pd.DataFrame, candidate_weights: list[dict[str, float]], k: int, positive_threshold: float, max_users: int = 300, sampled_cfg: dict[str, Any] | None = None) -> dict[str, float]:
    sampled_cfg = sampled_cfg or {}
    hybrid = models.get("Hybrid")
    if hybrid is None or not hasattr(hybrid, "set_weights") or val_ratings.empty:
        return {}
    best_weights = candidate_weights[0]
    best_score = -1.0
    eval_models = {"Hybrid": hybrid}
    tune_users = min(max_users, int(sampled_cfg.get("max_users", max_users) or max_users), 120)
    for weights in candidate_weights:
        hybrid.set_weights(weights)
        random_rows, _ = sampled_ranking_eval(eval_models, train_ratings, val_ratings, movies_df, k, positive_threshold, num_negatives=int(sampled_cfg.get("num_negatives", 49)), max_users=tune_users, seed=2026, mode="random")
        pop_rows, _ = sampled_ranking_eval(eval_models, train_ratings, val_ratings, movies_df, k, positive_threshold, num_negatives=int(sampled_cfg.get("num_negatives", 49)), max_users=tune_users, seed=2027, mode="popaware", num_buckets=int(sampled_cfg.get("popaware", {}).get("num_buckets", 10)), adjacent_buckets=int(sampled_cfg.get("popaware", {}).get("adjacent_buckets", 1)), prefer_harder=bool(sampled_cfg.get("popaware", {}).get("prefer_harder", False)))
        full_rows, _ = full_ranking_eval(eval_models, train_ratings, val_ratings, movies_df, k, positive_threshold, max_users=min(tune_users, 40), seed=2028)
        r = random_rows[0] if random_rows else {}
        p = pop_rows[0] if pop_rows else {}
        f = full_rows[0] if full_rows else {}
        objective = 0.60 * float(p.get("ndcg@10", 0.0)) + 0.25 * float(r.get("ndcg@10", 0.0)) + 0.15 * float(f.get("ndcg@10", 0.0))
        if objective > best_score:
            best_score = objective
            best_weights = weights
    hybrid.set_weights(best_weights)
    return best_weights


def evaluate_models(
    models: dict[str, object],
    train_ratings: pd.DataFrame,
    test_ratings: pd.DataFrame,
    movies_df: pd.DataFrame,
    output_table_path: str | Path,
    output_figure_path: str | Path,
    k: int = 10,
    positive_threshold: float = 4.0,
    max_users: int | None = None,
    sampled_cfg: dict[str, Any] | None = None,
    best_hybrid_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    sampled_cfg = sampled_cfg or {}
    seed = int(sampled_cfg.get("seed", 42))
    logger.info("Running rating prediction evaluation.")
    rating_rows = rating_prediction_eval(models, test_ratings)
    logger.info("Running full-ranking evaluation.")
    full_rows, full_users = full_ranking_eval(models, train_ratings, test_ratings, movies_df, k, positive_threshold, max_users=max_users, seed=seed)
    logger.info("Running random sampled-ranking evaluation.")
    sampled_random, random_users = sampled_ranking_eval(models, train_ratings, test_ratings, movies_df, k, positive_threshold, num_negatives=int(sampled_cfg.get("num_negatives", 99)), max_users=sampled_cfg.get("max_users", max_users), seed=seed, mode="random") if sampled_cfg.get("enabled", True) else ([], 0)
    logger.info("Running popularity-aware sampled-ranking evaluation.")
    sampled_popaware, popaware_users = sampled_ranking_eval(models, train_ratings, test_ratings, movies_df, k, positive_threshold, num_negatives=int(sampled_cfg.get("num_negatives", 99)), max_users=sampled_cfg.get("max_users", max_users), seed=seed, mode="popaware", num_buckets=int(sampled_cfg.get("popaware", {}).get("num_buckets", 10)), adjacent_buckets=int(sampled_cfg.get("popaware", {}).get("adjacent_buckets", 1)), prefer_harder=bool(sampled_cfg.get("popaware", {}).get("prefer_harder", False))) if sampled_cfg.get("popaware", {}).get("enabled", True) else ([], 0)

    output_table_path = Path(output_table_path)
    ensure_dir(output_table_path.parent)
    pd.DataFrame(full_rows).to_csv(output_table_path, index=False)
    pd.DataFrame(full_rows).to_csv("reports/tables/evaluation_full_ranking.csv", index=False)
    pd.DataFrame(sampled_random).to_csv("reports/tables/evaluation_sampled_random.csv", index=False)
    pd.DataFrame(sampled_popaware).to_csv("reports/tables/evaluation_sampled_popaware.csv", index=False)
    pd.DataFrame(rating_rows).to_csv("reports/tables/evaluation_rating_prediction.csv", index=False)
    ensure_dir(Path(output_figure_path).parent)
    _plot_metrics(pd.DataFrame(full_rows), pd.DataFrame(sampled_random), pd.DataFrame(sampled_popaware), output_figure_path)

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluated_users": {"full_ranking": full_users, "sampled_random": random_users, "sampled_popaware": popaware_users},
        "positive_threshold": positive_threshold,
        "k": k,
        "seed": seed,
        "num_negatives": int(sampled_cfg.get("num_negatives", 99)),
        "popaware_prefer_harder": bool(sampled_cfg.get("popaware", {}).get("prefer_harder", False)),
    }
    summary = _summary(full_rows, sampled_random, sampled_popaware, rating_rows)
    result = {
        "metadata": metadata,
        "rating_prediction": rating_rows,
        "full_ranking": full_rows,
        "sampled_random": sampled_random,
        "sampled_popaware": sampled_popaware,
        "legacy_sampled_ranking": sampled_random,
        "best_hybrid_weights": best_hybrid_weights or {},
        "summary": summary,
        "notes": {
            "rmse_mae_note": "RMSE/MAE are mainly meaningful for rating prediction models such as MF and UserCF.",
            "full_ranking_note": "Full-ranking evaluates recommendations from the whole catalog and is strict, so values are usually lower.",
            "sampled_random_note": "Random sampled-ranking is useful but can make popularity baselines look strong when negatives are too easy.",
            "sampled_popaware_note": "Popularity-aware sampled-ranking samples harder negatives from similar popularity buckets and better tests personalized ranking.",
        },
    }
    _write_explanation(result)
    return result


def _plot_metrics(full_df: pd.DataFrame, random_df: pd.DataFrame, popaware_df: pd.DataFrame, fig_path: str | Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(22, 6))
    for ax, df, title in [(axes[0], full_df, "Full-ranking"), (axes[1], random_df, "Random Sampled"), (axes[2], popaware_df, "Popularity-aware Sampled")]:
        if df.empty:
            ax.set_title(title)
            continue
        x = range(len(df))
        for c in ["precision@10", "recall@10", "ndcg@10", "coverage"]:
            if c in df:
                ax.plot(x, df[c], marker="o", label=c)
        ax.set_xticks(list(x))
        ax.set_xticklabels(df["model"], rotation=30)
        ax.set_title(title)
        ax.legend()
    fig.tight_layout()
    fig.savefig(fig_path, dpi=180)
    plt.close(fig)


def _metric_value(row: dict, metric: str) -> float | None:
    aliases = {
        "ndcg@10": ["ndcg@10", "ndcg_at_10", "ndcg10", "ndcg"],
        "precision@10": ["precision@10", "precision_at_10", "precision10", "precision"],
        "recall@10": ["recall@10", "recall_at_10", "recall10", "recall"],
        "hitrate@10": ["hitrate@10", "hit_rate@10", "hitrate_at_10", "hit_rate_at_10", "hitrate"],
        "coverage": ["coverage"],
        "rmse": ["rmse"],
    }
    for key in aliases.get(metric, [metric]):
        value = row.get(key)
        if value is not None:
            try:
                return float(value)
            except Exception:
                return None
    return None


def _best(rows: list[dict], metric: str, reverse: bool = True) -> str:
    if not rows:
        return "N/A"
    fn = max if reverse else min
    fallback = -1e18 if reverse else 1e18
    return fn(rows, key=lambda r: _metric_value(r, metric) if _metric_value(r, metric) is not None else fallback).get("model", "N/A")


def _summary(full_rows: list[dict], random_rows: list[dict], popaware_rows: list[dict], rating_rows: list[dict]) -> dict[str, str]:
    rating_valid = [r for r in rating_rows if r.get("rmse") is not None]
    coverage_rows = full_rows if full_rows else popaware_rows
    coverage_source = "full_ranking" if full_rows else "sampled_popaware"
    return {
        "best_rating_predictor": _best(rating_valid, "rmse", reverse=False),
        "best_full_ranking_model": _best(full_rows, "ndcg@10"),
        "best_sampled_random_model": _best(random_rows, "ndcg@10"),
        "best_sampled_popaware_model": _best(popaware_rows, "ndcg@10"),
        "best_coverage_model": _best(coverage_rows, "coverage"),
        "best_coverage_source": coverage_source,
        "best_interpretable_model": "ItemCF",
        "best_cold_start_model": "Popularity / ContentBased",
        "best_cold_start_note": "Popularity works for users with no history; ContentBased works for declared preferences and similar-movie discovery.",
    }


def _write_explanation(result: dict[str, Any]) -> None:
    ensure_dir("reports")
    summary = result.get("summary", {})
    text = f"""# Evaluation Explanation

## Algorithm roles
- Popularity: a non-personalized baseline for cold start and trending shelves.
- UserCF: user-neighborhood collaborative filtering, useful when similar users have overlapping history.
- ItemCF: item-neighborhood collaborative filtering, strong for explainable recommendations such as "Because you liked ...".
- MatrixFactorization / SVD: rating prediction model that captures latent user and movie factors.
- ContentBased: semantic matching from genres, tags, keywords, cast, director, and overview; best suited for cold start, Discover, and Similar Movies.
- Hybrid: blends all signals to improve ranking stability and product usefulness.

## Metrics
Precision@K measures how many of the top K recommendations are positive. Recall@K measures how many held-out positives are recovered. HitRate@K checks whether at least one positive appears. NDCG@K rewards placing positives near the top. Coverage measures catalog breadth. RMSE/MAE measure explicit rating prediction error and are mainly meaningful for MF/UserCF/ItemCF.

## Why there are three ranking evaluations
Full-ranking asks a model to find the user's future high-rated movies from the entire movie catalog. This is the strictest setup, so Precision@10, Recall@10, and NDCG@10 are naturally low: the model has thousands of plausible candidates and only a few held-out positives.

Random sampled-ranking builds a smaller candidate set from held-out positives plus random unseen negatives. Scores are usually higher because many random negatives are obscure or weakly related to the user.

Popularity-aware sampled-ranking is stricter than random sampled-ranking. It samples negatives from similar or harder popularity buckets, so a Popularity model cannot win only by ranking globally popular movies above obscure negatives. This setting better tests personalized ranking ability.

## Why MF/SVD is strong for rating prediction
MF/SVD directly optimizes explicit rating prediction, so RMSE and MAE are the right metrics for it. In the current run, the best rating prediction model is {summary.get('best_rating_predictor', 'N/A')}.

## Why ItemCF is strong for explainable recommendation
ItemCF supports source-movie explanations such as "Because you liked ...". It also tends to produce broader catalog exposure, which is why it is often a strong coverage and interpretability baseline.

## Why Hybrid is the comprehensive framework
Hybrid normalizes each model's score per user and combines popularity, UserCF, ItemCF, MF, and content evidence. It is a fusion framework rather than a guarantee of winning every metric. Hybrid can be strongest under one evaluation, while stricter popularity-aware evaluation may favor ItemCF or another specialized model. This is useful in a course defense because it shows the complementary strengths of different recommenders.

## Popularity and ContentBased interpretation
Popularity can achieve high recall when held-out positives are mainstream, but it has weak personalization and often low coverage. ContentBased may not dominate full-ranking metrics, but it is important for cold-start discovery, semantic similar-movie pages, and explanation quality.

## Current strongest models
- Best rating prediction model: {summary.get('best_rating_predictor', 'N/A')}
- Best full-ranking model: {summary.get('best_full_ranking_model', 'N/A')}
- Best random sampled-ranking model: {summary.get('best_sampled_random_model', 'N/A')}
- Best popularity-aware sampled-ranking model: {summary.get('best_sampled_popaware_model', 'N/A')}
- Best coverage model: {summary.get('best_coverage_model', 'N/A')} ({summary.get('best_coverage_source', 'N/A')})
- Best interpretable model: {summary.get('best_interpretable_model', 'ItemCF')}
- Best cold-start models: {summary.get('best_cold_start_model', 'Popularity / ContentBased')}
"""
    Path("reports/evaluation_explanation.md").write_text(text, encoding="utf-8")
