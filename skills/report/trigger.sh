#!/bin/bash
# 장 마감 리포트 트리거 — launchd에서 호출
# Claude Code 에이전트 모드로 리포트 생성

set -e

PROJECT_DIR="/Users/afred/Projects/Alfred"
CLAUDE="/Users/afred/.local/bin/claude"
LOG_DIR="$PROJECT_DIR/run/logs"
LOG_FILE="$LOG_DIR/report-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"

echo "[$(date)] 장 마감 리포트 시작" >> "$LOG_FILE"

$CLAUDE --dangerously-skip-permissions \
  --model sonnet \
  -p "장 마감 리포트를 생성해줘. 순서: 1) python3 skills/stock/fetch_stock.py로 최신 데이터 수집 2) data/stock.json 읽고 분석 3) skills/report/SKILL.md의 리포트 형식대로 작성 4) skills/research/save_note.py의 md_to_html, _save_to_notes로 Apple Notes 'Alfred' 폴더에 저장. 노트 제목은 '장 마감 리포트 (M/DD)' 형식." \
  >> "$LOG_FILE" 2>&1

echo "[$(date)] 완료 (exit: $?)" >> "$LOG_FILE"
