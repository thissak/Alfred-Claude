"""메모리 관리 — Markdown 파일 기반 기억 저장/로딩."""

import json
import os
import re
from datetime import datetime

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "memory")

# [MEM:about] 내용, [MEM:calendar] 내용, [MEM:notes] 내용
MEM_PATTERN = re.compile(r"\[MEM:(\w+)\]\s*(.+)")

VALID_TYPES = {"about", "calendar", "notes"}


def init():
    """memory/ 디렉토리와 기본 파일 초기화."""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    for name in VALID_TYPES:
        path = os.path.join(MEMORY_DIR, f"{name}.md")
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(f"# {name}\n\n")


def load_all():
    """모든 메모리 파일을 읽어 하나의 문자열로 반환."""
    sections = []
    for name in sorted(VALID_TYPES):
        path = os.path.join(MEMORY_DIR, f"{name}.md")
        if os.path.exists(path):
            content = open(path).read().strip()
            if content and content != f"# {name}":
                sections.append(content)
    return "\n\n".join(sections) if sections else ""


def parse_and_save(response):
    """응답에서 [MEM:xxx] 파싱 → 파일 저장 → 클린 응답 반환."""
    lines = response.split("\n")
    clean_lines = []
    memories = []

    for line in lines:
        match = MEM_PATTERN.match(line.strip())
        if match:
            mem_type, content = match.group(1), match.group(2).strip()
            if mem_type in VALID_TYPES:
                memories.append((mem_type, content))
        else:
            clean_lines.append(line)

    # 메모리 저장
    for mem_type, content in memories:
        _append_memory(mem_type, content)

    # 클린 응답 (뒤쪽 빈 줄 제거)
    clean = "\n".join(clean_lines).rstrip()
    if memories:
        saved = ", ".join(f"{t}:{c[:20]}" for t, c in memories)
        print(f"[기억 저장] {saved}")
    return clean


def _append_memory(mem_type, content):
    """메모리 파일에 내용 추가."""
    path = os.path.join(MEMORY_DIR, f"{mem_type}.md")
    timestamp = datetime.now().strftime("%Y-%m-%d")
    with open(path, "a") as f:
        f.write(f"- {content} ({timestamp})\n")


def log_history(user_msg, reply):
    """대화 기록을 history.jsonl에 추가."""
    path = os.path.join(MEMORY_DIR, "history.jsonl")
    entry = {
        "ts": datetime.now().isoformat(),
        "user": user_msg,
        "alf": reply,
    }
    with open(path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
