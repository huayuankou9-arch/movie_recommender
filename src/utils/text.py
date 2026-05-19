from __future__ import annotations

import ast
import re
from typing import Any


def clean_title(title: str) -> str:
    if not isinstance(title, str):
        return ""
    text = re.sub(r"\(\d{4}\)", "", title)
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_year_from_title(title: str) -> int | None:
    if not isinstance(title, str):
        return None
    match = re.search(r"\((\d{4})\)", title)
    return int(match.group(1)) if match else None


def safe_literal_eval(value: Any, fallback: Any = None) -> Any:
    if fallback is None:
        fallback = []
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return fallback
    stripped = value.strip()
    if stripped in {"", "nan", "None", "null"}:
        return fallback
    try:
        return ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        return fallback
