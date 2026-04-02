#!/bin/bash
# Daily Surge 스크리닝 트리거 — launchd에서 호출

set -e

PROJECT_DIR="/Users/afred/Projects/Alfred-Claude"
export PATH="/opt/homebrew/bin:/Users/afred/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "$PROJECT_DIR"

python3 skills/report/daily_surge_manager.py
