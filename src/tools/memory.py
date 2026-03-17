"""메모리 저장/히스토리 기록 tool."""

import importlib


def _load_legacy_memory():
    try:
        return importlib.import_module("src.memory")
    except ModuleNotFoundError:
        return importlib.import_module("memory")


legacy_memory = _load_legacy_memory()
INLINE_MEM_PATTERN = legacy_memory.MEM_PATTERN


def clean_and_store(response):
    """응답에서 [MEM:*] 태그를 제거하고 메모리를 저장한다.

    legacy memory.parse_and_save()를 그대로 쓰지 않고,
    row id를 항목별로 추적해서 QMD 파일이 덮어써지지 않게 저장한다.
    """
    lines = response.split("\n")
    clean_lines = []
    memories = []

    for line in lines:
        stripped = line.strip()
        match = INLINE_MEM_PATTERN.match(stripped)
        if match:
            mem_type, content = match.group(1), match.group(2).strip()
            if mem_type in legacy_memory.VALID_TYPES and content:
                memories.append((mem_type, content))
            continue

        if "[MEM:" not in line:
            clean_lines.append(line)
            continue

        remaining = line
        for mem_match in INLINE_MEM_PATTERN.finditer(line):
            mem_type, content = mem_match.group(1), mem_match.group(2).strip()
            if mem_type in legacy_memory.VALID_TYPES and content:
                memories.append((mem_type, content))
                remaining = remaining.replace(mem_match.group(0), "").rstrip()
        if remaining.strip():
            clean_lines.append(remaining.rstrip())

    if not memories:
        return response.rstrip(), []

    conn = legacy_memory._get_conn()
    saved = []
    for mem_type, content in memories:
        cur = conn.execute(
            "INSERT INTO memories (type, content) VALUES (?, ?)",
            (mem_type, content),
        )
        mem_id = cur.lastrowid
        saved.append({"id": mem_id, "type": mem_type, "content": content})

    conn.commit()
    print("[tool.memory] saved " + ", ".join(f"{m['type']}:{m['content'][:20]}" for m in saved))

    for item in saved:
        legacy_memory._sync_memory_to_qmd(item["type"], item["content"], item["id"])

    return "\n".join(clean_lines).rstrip(), saved


def log_history(user_msg, reply):
    """대화 히스토리 기록."""
    legacy_memory.log_history(user_msg, reply)
