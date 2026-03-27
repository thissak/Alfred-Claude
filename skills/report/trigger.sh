#!/bin/bash
# 장 마감 리포트 트리거 — launchd에서 호출
# Claude Code 에이전트 모드로 리포트 생성

set -e

PROJECT_DIR="/Users/afred/Projects/Alfred-Claude"
CLAUDE="/Users/afred/.local/bin/claude"
LOG_DIR="$PROJECT_DIR/run/logs"
LOG_FILE="$LOG_DIR/report-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"

echo "[$(date)] 장 마감 리포트 시작" >> "$LOG_FILE"

$CLAUDE --dangerously-skip-permissions \
  --model sonnet \
  --system-prompt-file skills/report/system.md \
  -p "장 마감 리포트를 생성해줘." \
  >> "$LOG_FILE" 2>&1

echo "[$(date)] 완료 (exit: $?)" >> "$LOG_FILE"
