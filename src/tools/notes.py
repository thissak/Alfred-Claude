"""Apple Notes 저장 tool."""

import importlib.util
from pathlib import Path


def _load_save_note_module():
    module_path = (
        Path(__file__).resolve().parent.parent.parent
        / "skills"
        / "research"
        / "save_note.py"
    )
    spec = importlib.util.spec_from_file_location("alf_save_note", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


save_note = _load_save_note_module()


def clean_and_store(response):
    """응답에서 [NOTE:*] 블록을 제거하고 Apple Notes에 저장한다."""
    clean, saved = save_note.parse_and_save(response)
    return clean, saved
