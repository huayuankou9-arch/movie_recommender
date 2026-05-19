from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

from src.utils.json_utils import sanitize_for_json

router = APIRouter(prefix="/api", tags=["evaluation"])


@router.get("/evaluation")
def evaluation():
    try:
        path = Path("reports/tables/evaluation_results.csv")
        if not path.exists():
            raise HTTPException(status_code=404, detail="evaluation_results.csv not found")
        df = pd.read_csv(path)
        return sanitize_for_json({"items": df.to_dict(orient="records")})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load evaluation: {exc}") from exc
