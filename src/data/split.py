from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from scipy.sparse import csr_matrix, save_npz
from sklearn.preprocessing import LabelEncoder

from src.utils.io import ensure_dir


def train_test_split_by_time(ratings: pd.DataFrame, test_ratio: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    ratings = ratings.sort_values(["userId", "timestamp"]).reset_index(drop=True)
    train_parts: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []
    for _, grp in ratings.groupby("userId", sort=False):
        n = len(grp)
        if n <= 1:
            train_parts.append(grp)
            continue
        n_test = max(1, int(n * test_ratio))
        if n - n_test < 1:
            n_test = n - 1
        train_parts.append(grp.iloc[:-n_test])
        test_parts.append(grp.iloc[-n_test:])
    train = pd.concat(train_parts, ignore_index=True)
    test = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame(columns=ratings.columns)
    return train, test


def train_val_test_split_by_time(
    ratings: pd.DataFrame,
    train_ratio: float = 0.7,
    val_ratio: float = 0.1,
    test_ratio: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ratings = ratings.sort_values(["userId", "timestamp"]).reset_index(drop=True)
    train_parts: list[pd.DataFrame] = []
    val_parts: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []
    for _, grp in ratings.groupby("userId", sort=False):
        n = len(grp)
        if n <= 2:
            train_parts.append(grp.iloc[: max(1, n - 1)])
            if n > 1:
                test_parts.append(grp.iloc[-1:])
            continue
        n_test = max(1, int(round(n * test_ratio)))
        n_val = max(1, int(round(n * val_ratio))) if n >= 5 else 0
        if n - n_test - n_val < 1:
            overflow = 1 - (n - n_test - n_val)
            reduce_val = min(n_val, overflow)
            n_val -= reduce_val
            overflow -= reduce_val
            n_test = max(1, n_test - overflow)
        train_end = n - n_val - n_test
        val_end = n - n_test
        train_parts.append(grp.iloc[:train_end])
        if n_val > 0:
            val_parts.append(grp.iloc[train_end:val_end])
        test_parts.append(grp.iloc[val_end:])
    train = pd.concat(train_parts, ignore_index=True)
    val = pd.concat(val_parts, ignore_index=True) if val_parts else pd.DataFrame(columns=ratings.columns)
    test = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame(columns=ratings.columns)
    return train, val, test


def build_and_save_matrix(train: pd.DataFrame, processed_dir: str | Path) -> dict[str, object]:
    out_dir = ensure_dir(processed_dir)
    user_encoder = LabelEncoder()
    movie_encoder = LabelEncoder()
    uidx = user_encoder.fit_transform(train["userId"])
    midx = movie_encoder.fit_transform(train["movieId"])
    matrix = csr_matrix((train["rating"].values, (uidx, midx)))

    save_npz(out_dir / "user_item_matrix.npz", matrix)
    user_decoder = {int(i): int(uid) for i, uid in enumerate(user_encoder.classes_)}
    movie_decoder = {int(i): int(mid) for i, mid in enumerate(movie_encoder.classes_)}

    joblib.dump(user_encoder, out_dir / "user_encoder.pkl")
    joblib.dump(movie_encoder, out_dir / "movie_encoder.pkl")
    joblib.dump(user_decoder, out_dir / "user_decoder.pkl")
    joblib.dump(movie_decoder, out_dir / "movie_decoder.pkl")
    return {
        "matrix": matrix,
        "user_encoder": user_encoder,
        "movie_encoder": movie_encoder,
        "user_decoder": user_decoder,
        "movie_decoder": movie_decoder,
    }
