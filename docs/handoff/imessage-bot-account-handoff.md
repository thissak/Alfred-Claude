# iMessage Bot 계정 세팅 Handoff

## 현재 상태
- Apple ID `alfred77bot@gmail.com` 생성 완료
- Mac Mini Messages 앱에 로그인 완료
- **iMessage 활성화 대기 중** (2026-03-02 생성, 최대 24시간 소요)

## 다음 작업
1. iMessage 활성화 확인
   - iPhone에서 `alfred77bot@gmail.com`으로 메시지 전송
   - **파란색 버블** = 활성화 완료 → 다음 단계 진행
   - **초록색 버블** = 아직 대기 중 → 추가 대기
2. 활성화 확인 후 `.env`의 대상 설정을 bot 계정 기준으로 업데이트
3. `src/alf.py`에서 bot 계정으로 수발신 테스트

## 알려진 이슈
- 새 Apple ID는 iMessage 활성화에 최대 24시간 소요
- 활성화 안 될 경우: Messages 로그아웃 → 재로그인, Wi-Fi 확인
