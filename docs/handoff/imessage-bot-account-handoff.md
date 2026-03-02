# iMessage Bot 계정 세팅 Handoff

## 완료된 작업
- Apple ID `alfred77bot@gmail.com` 생성 완료
- iMessage 활성화 확인됨 (2026-03-02)
- Mac Mini에 macOS 유저 `afred` 생성 완료
- GitHub private repo 생성: https://github.com/thissak/Alfred
- `.env` 포함하여 push 완료

## 현재 상태
- 메인 계정(에이아이머신)에서 개발/push 완료
- `afred` 계정은 아직 빈 상태 — 세팅 필요

## afred 계정에서 할 작업

### 1. 프로젝트 clone
```bash
git clone https://github.com/thissak/Alfred.git
cd Alfred
```
- GitHub 인증 필요 (private repo) → `gh auth login` 또는 HTTPS token 사용

### 2. Messages 앱 설정
- Messages 앱 열기 → `alfred77bot@gmail.com`으로 로그인
- iMessage 탭에서 활성화 확인

### 3. 권한 설정
- 시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 권한 → Terminal 추가
- 첫 실행 시 Automation 권한 팝업 허용

### 4. Python 환경
```bash
pip3 install python-dotenv
```

### 5. 실행 및 테스트
```bash
python3 src/alf.py
# "Alf 시작 — 감시 대상: +821097458966" 출력 확인
# iPhone에서 alfred77bot@gmail.com으로 메시지 전송 → 답장 확인
```

## 알려진 이슈
- Full Disk Access 미부여 시 `sqlite3.OperationalError: unable to open database file`
- Automation 미허용 시 osascript 발신 실패
- `afred` 계정에 `claude` CLI가 없을 수 있음 → Claude Max 로그인 필요
