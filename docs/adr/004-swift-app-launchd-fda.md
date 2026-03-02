# ADR 004: Swift .app 래퍼로 launchd FDA 해결

## Status
Accepted

## Context
launchd 데몬으로 chat.db에 접근하려면 전체 디스크 접근(FDA) 권한이 필요하다. macOS TCC는 FDA를 앱 번들 단위로 부여하는데, 셸 스크립트 .app은 TCC가 무시하고, Python 바이너리는 Apple 서명이라 직접 FDA 부여가 불가능했다.

## Decision
`daemon_ctl.py`가 Swift 소스를 컴파일하여 네이티브 Mach-O .app 번들을 생성한다. 이 .app이 Python 스크립트를 자식 프로세스로 실행하고, `AssociatedBundleIdentifiers` plist 키로 FDA를 전파한다. Ad-hoc 코드서명으로 TCC 인식을 보장한다.

추가로, launchd는 셸 PATH를 제공하지 않으므로 plist `EnvironmentVariables`에 `/opt/homebrew/bin` 등을 명시한다.

## Consequences
- chat.db 접근이 안정적으로 동작
- 데몬 추가 시 `daemon_ctl.py install <name>`으로 .app 빌드 + launchd 등록 자동화
- .app 재빌드 시 FDA 재등록 + 재부팅이 필요할 수 있음
- Xcode 불필요 (Command Line Tools의 swiftc만 사용)
