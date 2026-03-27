"""스크리너 필터 엔진 — 다중 조건 조합."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class Filter:
    """단일 필터 조건.

    op: ">=", "<=", ">", "<", "==", "!=", "between"
    value: 숫자 또는 (min, max) 튜플 (between용)
    """
    field: str
    op: str
    value: Any

    _OPS = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    def match(self, stock: dict) -> bool:
        v = stock.get(self.field)
        if v is None:
            return False
        if self.op == "between":
            lo, hi = self.value
            return lo <= v <= hi
        fn = self._OPS.get(self.op)
        if fn is None:
            raise ValueError(f"unknown op: {self.op}")
        return fn(v, self.value)

    def __repr__(self):
        return f"Filter({self.field} {self.op} {self.value})"


def apply_filters(
    stocks: list[dict],
    filters: list[Filter],
    sort_by: str | None = None,
    ascending: bool = True,
    limit: int | None = None,
) -> list[dict]:
    """필터 적용 (AND 조합) + 정렬 + 제한."""
    result = [s for s in stocks if all(f.match(s) for f in filters)]
    if sort_by:
        result.sort(key=lambda s: s.get(sort_by, 0) or 0, reverse=not ascending)
    if limit:
        result = result[:limit]
    return result


# --- 프리셋 ---

PRESETS: dict[str, list[Filter]] = {
    "저평가": [
        Filter("per", "between", (0, 15)),
        Filter("pbr", "<", 2),
    ],
    "모멘텀": [
        Filter("change_rate", ">", 0),
        Filter("volume", ">", 1000000),
    ],
    "수급": [
        Filter("foreign_net", ">", 0),
        Filter("volume", ">", 1000000),
    ],
    "대형주": [
        Filter("mktcap", ">", 100000),  # 시총 10조+
        Filter("per", ">", 0),
    ],
    "성장": [
        Filter("eps", ">", 0),
        Filter("change_rate", ">", 0),
        Filter("per", ">", 0),
    ],
}
