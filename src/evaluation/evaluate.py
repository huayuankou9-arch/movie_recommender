from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.evaluation.metrics import coverage, mae, ndcg_at_k, precision_at_k, recall_at_k, hit_rate_at_k, rmse
from src.utils.io import ensure_dir, read_json, write_json

RATING_MODELS = {"UserCF", "ItemCF", "MatrixFactorization"}


def _score_candidates(model: object, user_id: int, candidates: list[int]) -> dict[int, float]:
    if hasattr(model, "score_items"):
        return getattr(model, "score_items")(user_id, candidates)
    return {mid: float(model.score(user_id, mid)) for mid in candidates}


def _round_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in row.items():
        if isinstance(v, float):
            out[k] = round(v, 6)
        else:
            out[k] = v
    return out


def _positives_by_user(ratings: pd.DataFrame, positive_threshold: float) -> dict[int, set[int]]:
    return (
        ratings[ratings["rating"] >= positive_threshold]
        .groupby("userId")["movieId"]
        .apply(lambda x: set(x.astype(int).tolist()))
        .to_dict()
    )


def rating_prediction_eval(models: dict[str, object], test_ratings: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for model_name, model in models.items():
        if model_name not in RATING_MODELS:
            rows.append({"model": model_name, "rmse": None, "mae": None})
            continue
        y_true, y_pred = [], []
        for row in test_ratings.itertuples(index=False):
            y_true.append(float(row.rating))
            y_pred.append(float(np.clip(model.score(int(row.userId), int(row.movieId)), 0.5, 5.0)))
        rows.append(_round_row({"model": model_name, "rmse": rmse(y_true, y_pred), "mae": mae(y_true, y_pred)}))
    return rows


def full_ranking_eval(models: dict[str, object], test_ratings: pd.DataFrame, movies_df: pd.DataFrame, k: int, positive_threshold: float, max_users: int | None = None) -> list[dict[str, Any]]:
    positives = _positives_by_user(test_ratings, positive_threshold)
    user_ids = list(positives.keys())
    if max_users and len(user_ids) > max_users:
        user_ids = user_ids[:max_users]
    all_items = set(movies_df["movieId"].astype(int).tolist())
    rows = []
    for model_name, model in models.items():
        p_list: list[float] = []
        r_list: list[float] = []
        h_list: list[float] = []
        n_list: list[float] = []
        all_recs: list[int] = []
        for uid in user_ids:
            recs = model.recommend(int(uid), top_k=k, exclude_seen=True)
            rec_ids = [int(x["movieId"]) for x in recs]
            all_recs.extend(rec_ids)
            pos = positives.get(uid, set())
            p_list.append(precision_at_k(rec_ids, pos, k))
            r_list.append(recall_at_k(rec_ids, pos, k))
            h_list.append(hit_rate_at_k(rec_ids, pos, k))
            n_list.append(ndcg_at_k(rec_ids, pos, k))
        rows.append(
            _round_row(
                {
                    "model": model_name,
                    "precision@10": float(np.mean(p_list)) if p_list else 0.0,
                    "recall@10": float(np.mean(r_list)) if r_list else 0.0,
                    "hitrate@10": float(np.mean(h_list)) if h_list else 0.0,
                    "ndcg@10": float(np.mean(n_list)) if n_list else 0.0,
                    "coverage": coverage(all_recs, all_items),
                }
            )
        )
    return rows


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
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    positives = _positives_by_user(test_ratings, positive_threshold)
    train_seen = train_ratings.groupby("userId")["movieId"].apply(lambda x: set(x.astype(int))).to_dict()
    test_seen = test_ratings.groupby("userId")["movieId"].apply(lambda x: set(x.astype(int))).to_dict()
    all_items = np.array(movies_df["movieId"].astype(int).unique())
    user_ids = list(positives.keys())
    if max_users and len(user_ids) > max_users:
        user_ids = user_ids[:max_users]
    user_candidates: dict[int, tuple[list[int], set[int]]] = {}
    for uid in user_ids:
        pos = positives.get(uid, set())
        if not pos:
            continue
        interacted = set(train_seen.get(uid, set())) | set(test_seen.get(uid, set()))
        negatives_pool = np.array([mid for mid in all_items if mid not in interacted])
        if len(negatives_pool) == 0:
            continue
        n_needed = min(num_negatives * max(1, len(pos)), len(negatives_pool))
        negs = rng.choice(negatives_pool, size=n_needed, replace=False).astype(int).tolist()
        candidates = list(pos) + negs
        user_candidates[int(uid)] = (candidates, pos)

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
        rows.append(
            _round_row(
                {
                    "model": model_name,
                    "precision@10": float(np.mean(p_list)) if p_list else 0.0,
                    "recall@10": float(np.mean(r_list)) if r_list else 0.0,
                    "hitrate@10": float(np.mean(h_list)) if h_list else 0.0,
                    "ndcg@10": float(np.mean(n_list)) if n_list else 0.0,
                    "coverage": coverage(all_recs, set(all_items.astype(int))),
                }
            )
        )
    return rows


def tune_hybrid_weights(models: dict[str, object], train_ratings: pd.DataFrame, val_ratings: pd.DataFrame, movies_df: pd.DataFrame, candidate_weights: list[dict[str, float]], k: int, positive_threshold: float, max_users: int = 300) -> dict[str, float]:
    hybrid = models.get("Hybrid")
    if hybrid is None or not hasattr(hybrid, "set_weights") or val_ratings.empty:
        return {}
    best_weights = candidate_weights[0]
    best_tuple = (-1.0, -1.0, -1.0, -1.0)
    eval_models = {"Hybrid": hybrid}
    for weights in candidate_weights:
        hybrid.set_weights(weights)
        rows = sampled_ranking_eval(eval_models, train_ratings, val_ratings, movies_df, k, positive_threshold, num_negatives=49, max_users=max_users, seed=2026)
        row = rows[0] if rows else {}
        score_tuple = (row.get("ndcg@10", 0.0), row.get("recall@10", 0.0), row.get("hitrate@10", 0.0), row.get("precision@10", 0.0))
        if score_tuple > best_tuple:
            best_tuple = score_tuple
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
    rating_rows = rating_prediction_eval(models, test_ratings)
    full_rows = full_ranking_eval(models, test_ratings, movies_df, k, positive_threshold, max_users=max_users)
    sampled_rows = sampled_ranking_eval(
        models,
        train_ratings,
        test_ratings,
        movies_df,
        k,
        positive_threshold,
        num_negatives=int(sampled_cfg.get("num_negatives", 99)),
        max_users=sampled_cfg.get("max_users", max_users),
        seed=int(sampled_cfg.get("seed", 42)),
    ) if sampled_cfg.get("enabled", True) else []

    output_table_path = Path(output_table_path)
    ensure_dir(output_table_path.parent)
    pd.DataFrame(full_rows).to_csv(output_table_path, index=False)
    pd.DataFrame(full_rows).to_csv("reports/tables/evaluation_full_ranking.csv", index=False)
    pd.DataFrame(sampled_rows).to_csv("reports/tables/evaluation_sampled_ranking.csv", index=False)
    pd.DataFrame(rating_rows).to_csv("reports/tables/evaluation_rating_prediction.csv", index=False)
    ensure_dir(Path(output_figure_path).parent)
    _plot_metrics(pd.DataFrame(full_rows), pd.DataFrame(sampled_rows), output_figure_path)

    result = {
        "full_ranking": full_rows,
        "sampled_ranking": sampled_rows,
        "rating_prediction": rating_rows,
        "best_hybrid_weights": best_hybrid_weights or {},
        "notes": {
            "rmse_mae_note": "RMSE/MAE are mainly meaningful for rating prediction models such as MF and UserCF.",
            "sampled_eval_note": "Sampled ranking evaluates the model's ability to rank held-out positives against sampled negatives.",
        },
    }
    _write_explanation(result)
    return result


def _plot_metrics(full_df: pd.DataFrame, sampled_df: pd.DataFrame, fig_path: str | Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    for ax, df, title in [(axes[0], full_df, "Full-ranking Metrics"), (axes[1], sampled_df, "Sampled-ranking Metrics")]:
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


def _best(rows: list[dict], metric: str) -> str:
    if not rows:
        return "N/A"
    return max(rows, key=lambda r: (r.get(metric) or 0)).get("model", "N/A")


def _write_explanation(result: dict[str, Any]) -> None:
    ensure_dir("reports")
    rating_rows = [r for r in result.get("rating_prediction", []) if r.get("rmse") is not None]
    best_rating = min(rating_rows, key=lambda r: r.get("rmse", 999)).get("model", "N/A") if rating_rows else "N/A"
    full_best = _best(result.get("full_ranking", []), "ndcg@10")
    sampled_best = _best(result.get("sampled_ranking", []), "ndcg@10")
    coverage_best = _best(result.get("full_ranking", []), "coverage")
    text = f"""# Evaluation Explanation

## Why RMSE/MAE are mainly for rating prediction
RMSE and MAE compare predicted explicit ratings against held-out ratings on the 0.5-5.0 scale. They are most meaningful for models that directly predict ratings, especially MatrixFactorization and UserCF. Popularity, ContentBased, and Hybrid often output ranking scores rather than calibrated ratings, so their RMSE/MAE are not emphasized.

## Why Top-N recommendation uses Precision@K, Recall@K, HitRate@K, and NDCG@K
A recommender product is usually judged by whether the top shelf contains relevant items. Precision@K measures concentration of relevant movies, Recall@K measures how much held-out preference is recovered, HitRate@K measures whether at least one positive appears, and NDCG@K rewards placing positives near the top.

## Full-ranking vs sampled-ranking
Full-ranking evaluates recommendations against the whole movie catalog and is strict. Sampled-ranking compares held-out positives against sampled negatives for each user, which is a common way to isolate ranking ability while keeping evaluation practical.

## Why Hybrid improves stability
Hybrid combines popularity, user-neighborhood, item-neighborhood, latent-factor, and content signals. This reduces the chance that one weak signal dominates and usually improves stability across users.

## Current strongest models
- Best rating prediction model: {best_rating}
- Best Top-N model under full ranking: {full_best}
- Best Top-N model under sampled ranking: {sampled_best}
- Best coverage model: {coverage_best}
"""
    Path("reports/evaluation_explanation.md").write_text(text, encoding="utf-8")
