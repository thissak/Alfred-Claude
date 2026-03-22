"""오케스트레이터용 메시지 컨텍스트 조립.

1M 컨텍스트를 활용해 전체 메모리+히스토리를 주입한다.
별도 recall/검색 레이어 없이 LLM이 직접 시맨틱 매칭 수행.
"""

import importlib


def _load_legacy_memory():
    try:
        return importlib.import_module("src.memory")
    except ModuleNotFoundError:
        return importlib.import_module("memory")


legacy_memory = _load_legacy_memory()


def build_message_context(message):
    """전체 메모리 + 전체 히스토리를 컨텍스트로 조립."""
    sections = []

    try:
        memory_context = legacy_memory.load_all()
    except Exception as exc:
        print(f"[runtime.context] memory load error: {exc}")
        memory_context = ""

    if memory_context:
        sections.append("## Saved Memory\n" + memory_context)

    try:
        history_context = legacy_memory.load_history()
    except Exception as exc:
        print(f"[runtime.context] history load error: {exc}")
        history_context = ""

    if history_context:
        sections.append("## Conversation History\n" + history_context)

    return "\n\n".join(sections)
