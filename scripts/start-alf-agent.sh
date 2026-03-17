#!/bin/zsh
# Alf Agent — tmux + Claude Code + /loop 으로 inbox 감시
# Usage: ./scripts/start-alf-agent.sh

SESSION="alf-agent"
LOOP_PROMPT='/loop 1m run/inbox 디렉토리를 확인해서 *.json 파일이 있으면 각각 읽고, 메시지에 대한 응답을 작성해서 run/outbox/에 JSON으로 저장하고, 처리한 inbox 파일은 삭제해. 응답 JSON 형식: {"recipient": sender값, "message": 응답내용, "timestamp": ISO형식}'

# 기존 세션 종료
tmux kill-session -t "$SESSION" 2>/dev/null
sleep 1

# 새 tmux 세션에서 Claude Code 시작 (dangerously-skip-permissions로 자동승인)
tmux new-session -d -s "$SESSION" -c /Users/afred/Projects/Alfred \
  'claude --model sonnet --dangerously-skip-permissions'

# Claude Code 로딩 대기 후 /loop 자동 입력
sleep 15
tmux send-keys -t "$SESSION" "$LOOP_PROMPT" Enter

echo "Alf Agent 시작됨"
echo "  세션: tmux attach -t $SESSION"
echo "  /loop 1m 자동 등록 (15초 후)"
