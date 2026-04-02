#!/usr/bin/env bash
# deploy.sh — 맥프로(SSOT) → 맥미니(런타임) rsync 배포
set -euo pipefail

REMOTE="afred@Ai-Mac-mini.local"
REMOTE_DIR="/Users/afred/Projects/Alfred-Claude"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

EXCLUDES=(
  run/
  logs/
  data/
  "memory/alf.db*"
  .env
  .claude/settings.local.json
  apps/
  .git/
  .pytest_cache/
)

EXCLUDE_ARGS=()
for e in "${EXCLUDES[@]}"; do
  EXCLUDE_ARGS+=(--exclude="$e")
done

# --- 옵션 ---
DRY_RUN=""
RESTART=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-n) DRY_RUN="--dry-run"; shift ;;
    --restart|-r) RESTART=1; shift ;;
    --help|-h)
      echo "Usage: $0 [--dry-run|-n] [--restart|-r] [daemon...]"
      echo "  --dry-run  변경 사항만 표시 (실제 배포 안 함)"
      echo "  --restart  배포 후 데몬 재시작 (이름 지정 시 해당 데몬만, 없으면 전체)"
      exit 0 ;;
    *) break ;;
  esac
done

# --- 배포 ---
echo "📦 배포: $LOCAL_DIR → $REMOTE:$REMOTE_DIR"
rsync -avz --delete $DRY_RUN "${EXCLUDE_ARGS[@]}" \
  "$LOCAL_DIR/" "$REMOTE:$REMOTE_DIR/"

if [[ -n "$DRY_RUN" ]]; then
  echo "--- dry-run 완료 (실제 변경 없음)"
  exit 0
fi

echo "✅ 배포 완료"

# --- 데몬 재시작 ---
if [[ -n "$RESTART" ]]; then
  DAEMONS=("$@")
  if [[ ${#DAEMONS[@]} -eq 0 ]]; then
    DAEMONS=(all)
  fi
  for d in "${DAEMONS[@]}"; do
    echo "🔄 재시작: $d"
    ssh "$REMOTE" "cd $REMOTE_DIR && python3 daemon_ctl.py install $d"
  done
  echo "--- 데몬 상태:"
  ssh "$REMOTE" "cd $REMOTE_DIR && python3 daemon_ctl.py status"
fi
