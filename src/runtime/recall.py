"""과거 대화/기억 recall 어댑터."""

import importlib


def _load_legacy_memory():
    try:
        return importlib.import_module("src.memory")
    except ModuleNotFoundError:
        return importlib.import_module("memory")


legacy_memory = _load_legacy_memory()


def recall(query, limit=5):
    """질의와 관련된 과거 기억/대화 회상."""
    try:
        return legacy_memory.recall(query, limit=limit)
    except Exception as exc:
        print(f"[runtime.recall] recall unavailable: {exc}")
        return ""
