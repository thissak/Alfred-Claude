"""프롬프트 조립 + Claude 호출."""

import json
import os
import subprocess
import re

from dotenv import load_dotenv

load_dotenv()

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")

ALF_MODEL_CHAT = os.environ.get("ALF_MODEL_CHAT", "sonnet")
ALF_MODEL_MEMORY = os.environ.get("ALF_MODEL_MEMORY", "sonnet")

# 기억/일정/메모 관련 키워드 — sonnet 사용 트리거
MEMORY_KEYWORDS = re.compile(
    r"기억|메모|일정|약속|스케줄|좋아|싫어|선호|습관|remember|memo|schedule",
    re.IGNORECASE,
)


def build_system_prompt(memory_context):
    """스킬 + 메모리를 조합하여 시스템 프롬프트 생성."""
    parts = []

    # 1. 베이스 페르소나
    base_path = os.path.join(SKILLS_DIR, "_base.md")
    if os.path.exists(base_path):
        parts.append(open(base_path).read().strip())

    # 2. trigger=always 스킬 로딩
    for skill_content in _load_skills():
        parts.append(skill_content)

    # 3. 메모리 컨텍스트
    if memory_context:
        parts.append(f"## 현재 기억\n\n{memory_context}")

    return "\n\n---\n\n".join(parts)


def _load_skills():
    """skills/*/SKILL.md 중 trigger=always인 것들의 전문 로딩."""
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills

    for name in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, name, "SKILL.md")
        if not os.path.isfile(skill_path):
            continue
        content = open(skill_path).read()

        # YAML frontmatter에서 trigger 확인
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                frontmatter = content[3:end]
                if "trigger: on-demand" in frontmatter:
                    continue
                # trigger: always 또는 미지정 → 로딩
                body = content[end + 3:].strip()
                skills.append(body)
            else:
                skills.append(content)
        else:
            skills.append(content)

    return skills


def select_model(message):
    """메시지 내용에 따라 모델 선택."""
    if MEMORY_KEYWORDS.search(message):
        return ALF_MODEL_MEMORY
    return ALF_MODEL_CHAT


def ask(message, memory_context):
    """시스템 프롬프트 조립 → Claude 호출 → 응답 반환."""
    system_prompt = build_system_prompt(memory_context)
    model = select_model(message)

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)  # 중첩 세션 방지

    cmd = [
        "claude", "-p",
        "--model", model,
        "--output-format", "json",
        "--system-prompt", system_prompt,
        message,
    ]

    print(f"[brain] model={model}, prompt={len(system_prompt)}자")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    if result.returncode != 0:
        print(f"[claude 에러] {result.stderr.strip()}")
        return None
    data = json.loads(result.stdout)
    return data["result"]
