# GCP 헬스 모니터

**생성일**: 2026-04-05
**배경**: GCP 결제 계정 체험판 만료로 전체 서비스 다운, 장애 감지 지연

---

## 구조

```
5분 간격 폴링
  → HTTP 헬스체크 (4개 엔드포인트)
  → 장애 시: gcloud 진단 수집 (read-only)
  → claude -p 원인 분석 (sonnet, max-turns 3)
  → iMessage 알림 (outbox → bridge)
```

## 체크 대상

| 이름 | URL | 프로젝트 |
|------|-----|---------|
| NTS | https://nts.etaxbook.co.kr/health | etaxbook-web |
| eBook | https://etaxbook.co.kr/health | etaxbook-web |
| Taxlaw API | https://taxlaw.etaxbook.co.kr/health | taxlaw-db-api |
| ES (검색) | https://taxlaw.etaxbook.co.kr/api/search?q=test&size=1 | taxlaw-db-api |

## 파일

| 파일 | 설명 |
|------|------|
| `daemons/health_monitor.py` | 데몬 본체 |
| `config/health-monitor-key.json` | GCP read-only 서비스 계정 키 (git 제외) |
| `run/health_status.json` | 엔드포인트별 마지막 상태 (런타임) |

## GCP 서비스 계정

| 항목 | 값 |
|------|-----|
| 계정 | health-monitor-reader@etaxbook-web.iam.gserviceaccount.com |
| 권한 | roles/viewer (etaxbook-web, taxlaw-db-api) |
| 키 파일 | `config/health-monitor-key.json` (Alfred), `EtaxbookMasterLabs/config/` (맥프로 백업) |

read-only 계정이므로 VM 시작/중지, 배포 등 수정 작업 불가.

## 알림 동작

- **장애 감지** (healthy -> down): gcloud 진단 + Claude 분석 + iMessage
- **복구 감지** (down -> healthy): 복구 알림 iMessage
- **상태 유지** (계속 ok / 계속 down): 로그만 기록, 알림 없음 (중복 방지)

## 운영

```bash
# 테스트 (1회 실행)
HEALTH_RUN_NOW=1 python daemons/health_monitor.py

# 데몬 시작/중지
python daemon_ctl.py start health
python daemon_ctl.py stop health

# 로그 확인
python daemon_ctl.py logs health -f

# launchd 등록 (프로덕션)
python daemon_ctl.py install health

# 상태 확인
python daemon_ctl.py status
```

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `HEALTH_INTERVAL` | 300 | 체크 간격 (초) |
| `ALF_MY_NUMBER` | (기존) | iMessage 수신자 |
| `HEALTH_RUN_NOW` | - | 1이면 즉시 1회 실행 후 종료 |
