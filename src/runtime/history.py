"""대화 히스토리 읽기 어댑터."""

import importlib


def _load_legacy_memory():
    try:
        return importlib.import_module("src.memory")
    except ModuleNotFoundError:
        return importlib.import_module("memory")


legacy_memory = _load_legacy_memory()


DEFAULT_HISTORY_LIMIT = 5


def get_recent_history(limit=DEFAULT_HISTORY_LIMIT):
    """최근 대화 히스토리 조회.

    기존 memory.py를 읽기 전용으로 감싼다. DB가 비었거나 초기화 전이면 빈 목록을 반환한다.
    """
    try:
        return legacy_memory.get_recent_history(limit)
    except Exception as exc:
        print(f"[runtime.history] recent history unavailable: {exc}")
        return []
