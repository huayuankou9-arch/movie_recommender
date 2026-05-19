from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.evaluation.metrics import mae, precision_recall_hit_ndcg_at_k, rmse
from src.utils.io import ensure_dir


def evaluate_models(
    models: dict[str, object],
    test_ratings: pd.DataFrame,
    movies_df: pd.DataFrame,
    output_table_path: str | Path,
    output_figure_path: str | Path,
    k: int = 10,
    positive_threshold: float = 4.0,
    max_users: int | None = None,
) -> pd.DataFrame:
    rows: list[dict] = []
    all_movies = set(movies_df["movieId"].astype(int).tolist())

    positives = (
        test_ratings[test_ratings["rating"] >= positive_threshold]
        .groupby("userId")["movieId"]
        .apply(lambda x: set(x.astype(int).tolist()))
        .to_dict()
    )
    user_ids = list(positives.keys())
    if max_users is not None and len(user_ids) > max_users:
        user_ids = user_ids[:max_users]
        positives = {uid: positives[uid] for uid in user_ids}

    for model_name, model in models.items():
        y_true: list[float] = []
        y_pred: list[float] = []
        for row in test_ratings.itertuples(index=False):
            y_true.append(float(row.rating))
            y_pred.append(float(model.score(int(row.userId), int(row.movieId))))
        model_rmse = rmse(y_true, y_pred)
        model_mae = mae(y_true, y_pred)

        p_list, r_list, h_list, n_list = [], [], [], []
        rec_movie_ids: set[int] = set()
        for user_id, pos_set in positives.items():
            recs = model.recommend(int(user_id), top_k=k, exclude_seen=True)
            rec_ids = [int(x["movieId"]) for x in recs]
            rec_movie_ids.update(rec_ids)
            p, r, h, n = precision_recall_hit_ndcg_at_k(rec_ids, pos_set, k)
            p_list.append(p)
            r_list.append(r)
            h_list.append(h)
            n_list.append(n)

        coverage = len(rec_movie_ids) / len(all_movies) if all_movies else 0.0
        rows.append(
            {
                "model": model_name,
                "rmse": round(model_rmse, 6),
                "mae": round(model_mae, 6),
                "precision@10": round(sum(p_list) / len(p_list), 6) if p_list else 0.0,
                "recall@10": round(sum(r_list) / len(r_list), 6) if r_list else 0.0,
                "hitrate@10": round(sum(h_list) / len(h_list), 6) if h_list else 0.0,
                "ndcg@10": round(sum(n_list) / len(n_list), 6) if n_list else 0.0,
                "coverage": round(coverage, 6),
            }
        )

    result = pd.DataFrame(rows)
    ensure_dir(Path(output_table_path).parent)
    ensure_dir(Path(output_figure_path).parent)
    result.to_csv(output_table_path, index=False)
    _plot_metrics(result, output_figure_path)
    return result


def _plot_metrics(df: pd.DataFrame, fig_path: str | Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    left_cols = ["precision@10", "recall@10", "ndcg@10", "coverage"]
    right_cols = ["rmse", "mae"]
    x = range(len(df))
    for c in left_cols:
        axes[0].plot(x, df[c], marker="o", label=c)
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(df["model"], rotation=30)
    axes[0].set_title("Ranking Metrics")
    axes[0].legend()
    for c in right_cols:
        axes[1].plot(x, df[c], marker="o", label=c)
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(df["model"], rotation=30)
    axes[1].set_title("Error Metrics")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(fig_path, dpi=180)
    plt.close(fig)
