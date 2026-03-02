# #1 네이버 IMAP IDLE 미지원으로 이메일 데몬 반복 에러

**Issue**: https://github.com/thissak/Alfred/issues/1
**Status**: Resolved
**Created**: 2026-03-03
**Resolved**: 2026-03-03

---

## 1. 문제
- 증상: `mb.idle.wait()` 호출 시 네이버 IMAP 서버가 `BAD Error in IMAP command IDLE: bad syntax` 반환, 30초마다 재접속 반복
- 재현: `daemons/email_daemon.py` 실행 시 매번 발생

## 2. 원인
네이버 IMAP 서버가 IDLE 명령을 지원하지 않음. `email_daemon.py:66`에서 `mb.idle.wait(timeout=IDLE_TIMEOUT)` 호출이 실패.

## 3. 수정

| 파일 | 변경 |
|------|------|
| `daemons/email_daemon.py` | IDLE → 폴링 방식으로 전환 |

```python
# Before: IDLE 대기 (네이버 미지원)
responses = mb.idle.wait(timeout=IDLE_TIMEOUT)

# After: 주기적 폴링
time.sleep(POLL_INTERVAL)
fetch_and_save(mb)
```

**PR**: -

## 4. 검증
- [x] 데몬 시작 후 IDLE 에러 없이 주기적 fetch 확인
- [ ] 새 메일 도착 시 다음 폴링에서 감지 확인 (5분 간격)
