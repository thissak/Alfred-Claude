"""오케스트레이터용 메시지 컨텍스트 조립."""

import importlib


def _load_legacy_memory():
    try:
        return importlib.import_module("src.memory")
    except ModuleNotFoundError:
        return importlib.import_module("memory")


legacy_memory = _load_legacy_memory()

try:
    from runtime.history import get_recent_history
    from runtime.recall import recall
except ModuleNotFoundError:
    from src.runtime.history import get_recent_history
    from src.runtime.recall import recall


def _format_history(history):
    if not history:
        return ""

    lines = ["## Recent Conversation"]
    for item in history:
        user_msg = item.get("user_msg", "").strip()
        alf_msg = item.get("alf_msg", "").strip()
        if user_msg:
            lines.append(f"User: {user_msg}")
        if alf_msg:
            if len(alf_msg) > 200:
                alf_msg = alf_msg[:200] + "..."
            lines.append(f"Assistant: {alf_msg}")
    return "\n".join(lines)


def _format_recall(recall_text):
    if not recall_text:
        return ""
    return "## Relevant Past Notes\n" + recall_text


def build_message_context(message):
    """현재 메시지 처리 전에 붙일 메모리 컨텍스트를 생성."""
    sections = []

    try:
        profile_context = legacy_memory.load_all()
    except Exception as exc:
        print(f"[runtime.context] memory load unavailable: {exc}")
        profile_context = ""

    if profile_context:
        sections.append("## Saved Memory\n" + profile_context)

    history = get_recent_history()
    history_section = _format_history(history)
    if history_section:
        sections.append(history_section)

    recall_section = _format_recall(recall(message))
    if recall_section:
        sections.append(recall_section)

    return "\n\n".join(sections)
