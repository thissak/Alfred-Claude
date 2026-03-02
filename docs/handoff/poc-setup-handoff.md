# POC 실행 전 세팅 Handoff

## 완료된 작업
- `src/alf.py` POC 구현 (chat.db 폴링 → Claude → osascript 답장)
- `.env` 생성 (`ALF_MY_NUMBER=+821097548966`)
- `python-dotenv` 설치 완료

## 다음 작업: 권한 설정

### 1. Full Disk Access (필수)
Terminal이 chat.db를 읽으려면 전체 디스크 접근 권한 필요.

- 시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 권한
- 하단 `+` 버튼 → `/Applications/Utilities/Terminal.app` 추가
- 토글 ON 확인
- **Terminal 재시작 필요** (권한 적용을 위해)

### 2. Automation 권한 (자동)
osascript가 Messages.app을 제어하는 권한. 첫 실행 시 팝업이 뜸.

- `python3 src/alf.py` 실행
- "Terminal이 Messages를 제어하려고 합니다" 팝업 → 허용
- 거부했을 경우: 시스템 설정 → 개인정보 보호 및 보안 → 자동화 → Terminal → Messages 토글 ON

### 3. Messages.app 실행
- Dock 또는 Spotlight에서 "메시지" 실행
- 내 번호로 기존 iMessage 대화가 하나 이상 있어야 함

## 검증 방법
```bash
# 1. Terminal 재시작 후
python3 src/alf.py
# "Alf 시작 — 감시 대상: +821097548966" 출력 확인

# 2. iPhone에서 Mac으로 iMessage 전송: "안녕 알프"

# 3. 2~5초 내 답장 수신 확인
```

## 알려진 이슈
- Full Disk Access 미부여 시 `sqlite3.OperationalError: unable to open database file`
- Automation 미허용 시 osascript 실행 에러 (발신 실패)
- Messages.app 미실행 시 osascript가 앱을 자동 실행하지만 buddy 조회 실패 가능
