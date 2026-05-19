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
